

import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

from alpaca_trade_api import REST

# ======================================================
# ALPACA CONFIG
# ======================================================
ALPACA_API_KEY = "PKU7NHFZQJZ665JLHO4YQAUJAS"
ALPACA_SECRET_KEY = "G3U4uRew9jfcq7ZAW4g9sJjyNmygoz4wZL7V5kK1AW3X"
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

alpaca = REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version="v2")

PAPER_TRADE_MODE = True   # True = send Alpaca paper trades

# ======================================================
# ALPACA ORDER FUNCTION
# ======================================================
def alpaca_trade(symbol, side, qty):
    try:
        alpaca.submit_order(
            symbol=symbol,
            qty=int(qty),
            side=side,
            type="market",
            time_in_force="day"
        )
        print(f"📈 ALPACA PAPER ORDER: {side.upper()} {int(qty)} {symbol}")
    except Exception as e:
        print("❌ Alpaca Order Error:", e)


# ======================================================
# STRATEGY CLASS
# ======================================================
class MA9_14_19_TradeLog:

    def __init__(self, start_date="2020-01-01", end_date=None, initial_capital=10000):
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        self.initial_capital = initial_capital
        self.portfolio_value = initial_capital
        self.position = "CASH"
        self.shares = 0

    def fetch_data(self):
        print("Fetching TQQQ & SQQQ data...")
        tqqq = yf.download("TQQQ", start=self.start_date, end=self.end_date, progress=False)
        sqqq = yf.download("SQQQ", start=self.start_date, end=self.end_date, progress=False)

        df = pd.DataFrame()
        df["TQQQ_Open"] = tqqq["Open"]
        df["TQQQ_Close"] = tqqq["Close"]
        df["SQQQ_Open"] = sqqq["Open"]
        df["SQQQ_Close"] = sqqq["Close"]
        return df.dropna()

    def calculate_signals(self, df):

        df["MA9"] = df["TQQQ_Close"].rolling(9).mean()
        df["MA14"] = df["TQQQ_Close"].rolling(14).mean()
        df["MA19"] = df["TQQQ_Close"].rolling(19).mean()
        df = df.dropna()

        df["Signal"] = "CASH"
        df["Reason"] = ""

        for i in range(len(df)):
            price = df["TQQQ_Close"].iloc[i]
            ma9 = df["MA9"].iloc[i]
            ma14 = df["MA14"].iloc[i]
            ma19 = df["MA19"].iloc[i]

            if price > ma19:
                df.iloc[i, df.columns.get_loc("Signal")] = "TQQQ"
                df.iloc[i, df.columns.get_loc("Reason")] = (
                    f"Price {price:.2f} > MA19 {ma19:.2f} → Strong uptrend"
                )

            elif price < ma14:
                df.iloc[i, df.columns.get_loc("Signal")] = "CASH"
                df.iloc[i, df.columns.get_loc("Reason")] = (
                    f"Price {price:.2f} < MA14 {ma14:.2f} → Weak trend → Stay in cash"
                )

            elif price < ma9:
                df.iloc[i, df.columns.get_loc("Signal")] = "SQQQ"
                df.iloc[i, df.columns.get_loc("Reason")] = (
                    f"Price {price:.2f} < MA9 {ma9:.2f} → Down momentum → SQQQ"
                )

        df["MA9_prev"] = df["MA9"].shift(1)
        df["MA14_prev"] = df["MA14"].shift(1)

        for i in range(1, len(df)):
            if (
                df["MA9"].iloc[i] > df["MA14"].iloc[i]
                and df["MA9_prev"].iloc[i] <= df["MA14_prev"].iloc[i]
                and df["Signal"].iloc[i] == "SQQQ"
            ):
                ma9 = df["MA9"].iloc[i]
                ma14 = df["MA14"].iloc[i]

                df.iloc[i, df.columns.get_loc("Signal")] = "CASH"
                df.iloc[i, df.columns.get_loc("Reason")] = (
                    f"MA9 {ma9:.2f} crossed above MA14 {ma14:.2f} → Exit SQQQ"
                )

        return df

    def execute_backtest(self, df):

        for i in range(len(df)-1):
            signal = df["Signal"].iloc[i]
            next_tqqq = df["TQQQ_Open"].iloc[i+1]
            next_sqqq = df["SQQQ_Open"].iloc[i+1]

            if signal != self.position:

                if self.position == "TQQQ":
                    self.portfolio_value = self.shares * next_tqqq
                elif self.position == "SQQQ":
                    self.portfolio_value = self.shares * next_sqqq

                if signal == "TQQQ":
                    self.shares = self.portfolio_value / next_tqqq
                elif signal == "SQQQ":
                    self.shares = self.portfolio_value / next_sqqq
                else:
                    self.shares = 0

                self.position = signal


# ======================================================
# LIVE EXECUTION
# ======================================================
def execute_today_trade(df, strategy):

    last = df.iloc[-1]

    price = last["TQQQ_Close"]
    ma9 = last["MA9"]
    ma14 = last["MA14"]
    ma19 = last["MA19"]
    signal = last["Signal"]
    reason = last["Reason"]

    print("\n================ REAL TIME MARKET STATE ================")
    print(f"TQQQ Price : {price:.2f}")
    print(f"MA9        : {ma9:.2f}")
    print(f"MA14       : {ma14:.2f}")
    print(f"MA19       : {ma19:.2f}")
    print("======================================================")

    print("\n📅 TODAY SIGNAL:", signal)
    print("🧠 Reason:", reason)

    if not PAPER_TRADE_MODE:
        return

    positions = alpaca.list_positions()
    current = [p.symbol for p in positions]

    if signal in current or (signal == "CASH" and len(current)==0):
        print("✓ Already aligned with signal.")
        return

    for p in positions:
        alpaca_trade(p.symbol, "sell", p.qty)

    if signal == "TQQQ":
        qty = strategy.portfolio_value / price
        alpaca_trade("TQQQ", "buy", qty)

    elif signal == "SQQQ":
        qty = strategy.portfolio_value / price
        alpaca_trade("SQQQ", "buy", qty)

    else:
        print("💤 Staying in CASH.")


# ======================================================
# MAIN
# ======================================================
def main():

    print("\nMA9/14/19 STRATEGY — EXPLAINABLE ALPACA BOT")

    strategy = MA9_14_19_TradeLog()

    df = strategy.fetch_data()
    df = strategy.calculate_signals(df)

    strategy.execute_backtest(df)

    execute_today_trade(df, strategy)

    print("\n✅ DONE")


if __name__ == "__main__":
    main()
