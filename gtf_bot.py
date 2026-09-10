import os
import requests
import yfinance as yf
import pandas as pd

# Load tokens from GitHub Secrets environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Tickers to scan (Add any NSE stocks ending in .NS)
WATCHLIST = [
    "RELIANCE.NS", "HDFCBANK.NS", "SBIN.NS", 
    "JSWINFRA.NS", "NMDC.NS", "IREDA.NS", "ONGC.NS", "NESTLEIND.NS"
]

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram secrets not configured!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def is_exciting(candle):
    rng = candle['High'] - candle['Low']
    if rng == 0: return False
    body = abs(candle['Close'] - candle['Open'])
    return (body / rng) > 0.50

def is_base(candle):
    rng = candle['High'] - candle['Low']
    if rng == 0: return False
    body = abs(candle['Close'] - candle['Open'])
    return (body / rng) <= 0.50

def evaluate_gtf_setup(ticker):
    print(f"Scanning {ticker}...")
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if len(df) < 30:
            return

        cmp = float(df['Close'].iloc[-1])
        
        # Scan recent candles for Reversals (DBR & RBD)
        for i in range(len(df) - 4, 3, -1):
            leg_in = df.iloc[i-1]
            base = df.iloc[i]
            leg_out = df.iloc[i+1]
            
            # 1. Drop-Base-Rally (Demand Reversal)
            if leg_in['Close'] < leg_in['Open'] and is_base(base) and leg_out['Close'] > leg_out['Open'] and is_exciting(leg_out):
                if leg_out['Close'] > leg_in['High']:
                    pl = float(max(base['Open'], base['Close']))
                    dl = float(min(leg_in['Low'], base['Low'], leg_out['Low']))
                    
                    subsequent_lows = df['Low'].iloc[i+2:]
                    tested = (subsequent_lows <= pl).any()
                    
                    # Proximity check: Price within 1.5% of Proximal Line
                    if not tested and cmp >= pl and ((cmp - pl) / pl) <= 0.015:
                        risk = pl - dl
                        t1 = pl + (2 * risk)
                        msg = (
                            f"🚨 *GTF DEMAND REVERSAL ALERT (DBR)*\n\n"
                            f"*Stock:* `{ticker}`\n"
                            f"*CMP:* ₹{cmp:.2f}\n"
                            f"*Zone:* PL = ₹{pl:.2f} | DL = ₹{dl:.2f}\n"
                            f"*Target 1 (2:1):* ₹{t1:.2f}\n"
                            f"*Status:* Fresh Zone retest approaching."
                        )
                        send_telegram_alert(msg)
                        break

            # 2. Rally-Base-Drop (Supply Reversal)
            if leg_in['Close'] > leg_in['Open'] and is_base(base) and leg_out['Close'] < leg_out['Open'] and is_exciting(leg_out):
                if leg_out['Close'] < leg_in['Low']:
                    pl = float(min(base['Open'], base['Close']))
                    dl = float(max(leg_in['High'], base['High'], leg_out['High']))
                    
                    subsequent_highs = df['High'].iloc[i+2:]
                    tested = (subsequent_highs >= pl).any()
                    
                    if not tested and cmp <= pl and ((pl - cmp) / pl) <= 0.015:
                        risk = dl - pl
                        t1 = pl - (2 * risk)
                        msg = (
                            f"⚠️ *GTF SUPPLY REVERSAL ALERT (RBD)*\n\n"
                            f"*Stock:* `{ticker}`\n"
                            f"*CMP:* ₹{cmp:.2f}\n"
                            f"*Zone:* PL = ₹{pl:.2f} | DL = ₹{dl:.2f}\n"
                            f"*Target 1 (2:1):* ₹{t1:.2f}\n"
                            f"*Status:* Fresh Supply retest approaching."
                        )
                        send_telegram_alert(msg)
                        break
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")

if __name__ == "__main__":
    for symbol in WATCHLIST:
        evaluate_gtf_setup(symbol)
