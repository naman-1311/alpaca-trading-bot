



import os
import yfinance as yf
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

from alpaca_trade_api import REST

# ======================================================
# ALPACA CONFIG (ENV VARIABLES)
# ======================================================
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL")

# DEBUG (temporary)
print("API KEY PRESENT:", ALPACA_API_KEY is not None)
print("SECRET PRESENT:", ALPACA_SECRET_KEY is not None)
print("BASE URL:", ALPACA_BASE_URL)

alpaca = REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version="v2")

PAPER_TRADE_MODE = True

# ======================================================
# SAFETY UTILITIES
# ======================================================
def market_is_ready(api):
    clock = api.get_clock()

    if not clock.is_open:
        print("❌ Market is closed. Exiting.")
        return False

    minutes_left = (clock.next_close - clock.timestamp).total_seconds() / 60
    print(f"⏰ Minutes to close: {round(minutes_left,2)}")

    if minutes_left > 15:
        print("⚠️ Too early before close. Exiting safely.")
        return False

    return True


def get_current_position():
    positions = alpaca.list_positions()
    if len(positions) == 0:
        return "CASH"
    return positions[0].symbol


# ======================================================
# ALPACA ORDER FUNCTION
# ======================================================
def alpaca_trade(symbol, side, qty):
    try:
        alpaca.submit_order(
            symbol=symbol,
            qty=int(float(qty)),
            side=side,
            type="market",
            time_in_force="day"
        )
        print(f"📈 ALPACA ORDER: {side.upper()} {int(float(qty))} {symbol}")
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
            p = df["TQQQ_Close"].iloc[i]
            ma9 = df["MA9"].iloc[i]
            ma14 = df["MA14"].iloc[i]
            ma19 = df["MA19"].iloc[i]

            if p > ma19:
                df.iloc[i, df.columns.get_loc("Signal")] = "TQQQ"
                df.iloc[i, df.columns.get_loc("Reason")] = f"Price {p:.2f} > MA19 {ma19:.2f}"

            elif p < ma14:
                df.iloc[i, df.columns.get_loc("Signal")] = "CASH"
                df.iloc[i, df.columns.get_loc("Reason")] = f"Price {p:.2f} < MA14 {ma14:.2f}"

            elif p < ma9:
                df.iloc[i, df.columns.get_loc("Signal")] = "SQQQ"
                df.iloc[i, df.columns.get_loc("Reason")] = f"Price {p:.2f} < MA9 {ma9:.2f}"

        df["MA9_prev"] = df["MA9"].shift(1)
        df["MA14_prev"] = df["MA14"].shift(1)

        for i in range(1, len(df)):
            if df["MA9"].iloc[i] > df["MA14"].iloc[i] and df["MA9_prev"].iloc[i] <= df["MA14_prev"].iloc[i]:
                if df["Signal"].iloc[i] == "SQQQ":
                    df.iloc[i, df.columns.get_loc("Signal")] = "CASH"
                    df.iloc[i, df.columns.get_loc("Reason")] = "MA9 crossed above MA14 → Exit SQQQ"

        return df


# ======================================================
# LIVE EXECUTION
# ======================================================
def execute_today_trade(df, strategy):

    if not market_is_ready(alpaca):
        return

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

    current_position = get_current_position()
    print("📌 Current Alpaca Position:", current_position)

    if signal == current_position:
        print("✓ Signal equals current position. No trade.")
        return

    if current_position != "CASH":
        alpaca_trade(current_position, "sell", alpaca.get_position(current_position).qty)

    if signal == "TQQQ":
        alpaca_trade("TQQQ", "buy", strategy.portfolio_value / price)

    elif signal == "SQQQ":
        alpaca_trade("SQQQ", "buy", strategy.portfolio_value / price)

    else:
        print("💤 Staying in CASH.")


# ======================================================
# MAIN
# ======================================================
def main():

    print("\nMA9/14/19 STRATEGY — PROFESSIONAL CLOUD BOT")

    strategy = MA9_14_19_TradeLog()

    df = strategy.fetch_data()
    df = strategy.calculate_signals(df)

    execute_today_trade(df, strategy)

    print("\n✅ BOT EXECUTION COMPLETE")


if __name__ == "__main__":
    main()
