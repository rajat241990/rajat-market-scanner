import os
import requests
import yfinance as yf

# Load tokens from GitHub Secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "SBIN.NS", 
    "JSWINFRA.NS", "NMDC.NS", "IREDA.NS", "ONGC.NS", "NESTLEIND.NS"
]

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram secrets missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})

def is_exciting(candle):
    rng = float(candle['High']) - float(candle['Low'])
    if rng == 0: return False
    body = abs(float(candle['Close']) - float(candle['Open']))
    return (body / rng) > 0.50

def is_base(candle):
    rng = float(candle['High']) - float(candle['Low'])
    if rng == 0: return False
    body = abs(float(candle['Close']) - float(candle['Open']))
    return (body / rng) <= 0.50

def evaluate_gtf_setup(ticker):
    print(f"Scanning {ticker}...")
    try:
        # BULLETPROOF FIX: Use yf.Ticker().history() instead of yf.download()
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo", interval="1d")
        
        if df.empty or len(df) < 30:
            print(f"Insufficient data for {ticker}")
            return

        cmp = float(df['Close'].iloc[-1])
        print(f"{ticker} CMP: ₹{cmp:.2f}")
        
        # Scan recent candles for Reversals (DBR & RBD)
        for i in range(len(df) - 4, 3, -1):
            leg_in = df.iloc[i-1]
            base = df.iloc[i]
            leg_out = df.iloc[i+1]

            in_open, in_close, in_high, in_low = float(leg_in['Open']), float(leg_in['Close']), float(leg_in['High']), float(leg_in['Low'])
            out_open, out_close, out_high, out_low = float(leg_out['Open']), float(leg_out['Close']), float(leg_out['High']), float(leg_out['Low'])
            base_open, base_close, base_high, base_low = float(base['Open']), float(base['Close']), float(base['High']), float(base['Low'])
            
            # 1. Drop-Base-Rally (Demand Reversal)
            if in_close < in_open and is_base(base) and out_close > out_open and is_exciting(leg_out):
                if out_close > in_high:
                    pl = max(base_open, base_close)
                    dl = min(in_low, base_low, out_low)
                    
                    subsequent_lows = df['Low'].iloc[i+2:].astype(float)
                    if not (subsequent_lows <= pl).any() and cmp >= pl and ((cmp - pl) / pl) <= 0.015:
                        risk = pl - dl
                        t1 = pl + (2 * risk)
                        send_telegram_alert(f"🚨 *GTF DEMAND ALERT (DBR)*\n*Stock:* `{ticker}`\n*CMP:* ₹{cmp:.2f}\n*Zone:* PL=₹{pl:.2f} | DL=₹{dl:.2f}\n*Target:* ₹{t1:.2f}")
                        break

            # 2. Rally-Base-Drop (Supply Reversal)
            if in_close > in_open and is_base(base) and out_close < out_open and is_exciting(leg_out):
                if out_close < in_low:
                    pl = min(base_open, base_close)
                    dl = max(in_high, base_high, out_high)
                    
                    subsequent_highs = df['High'].iloc[i+2:].astype(float)
                    if not (subsequent_highs >= pl).any() and cmp <= pl and ((pl - cmp) / pl) <= 0.015:
                        risk = dl - pl
                        t1 = pl - (2 * risk)
                        send_telegram_alert(f"⚠️ *GTF SUPPLY ALERT (RBD)*\n*Stock:* `{ticker}`\n*CMP:* ₹{cmp:.2f}\n*Zone:* PL=₹{pl:.2f} | DL=₹{dl:.2f}\n*Target:* ₹{t1:.2f}")
                        break
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")

if __name__ == "__main__":
    send_telegram_alert("🚀 *GTF Scanner Active:* Running analysis on watchlist...")
    for symbol in WATCHLIST:
        evaluate_gtf_setup(symbol)
