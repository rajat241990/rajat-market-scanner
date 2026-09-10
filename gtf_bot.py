 import os
import requests
import yfinance as yf

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

WATCHLIST = [
    "ABB.NS", "ADANIENT.NS", "ADANIGREEN.NS", "ADANIPORTS.NS", "ADANIPOWER.NS", "ATGL.NS", 
    "AMBUJACEM.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "DMART.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", 
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "BANKBARODA.NS", "BEL.NS", "BHARATFORG.NS", "BHEL.NS", 
    "BPCL.NS", "BHARTIARTL.NS", "BOSCHLTD.NS", "BRITANNIA.NS", "CANBK.NS", "CHOLAFIN.NS", 
    "CIPLA.NS", "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS", "CONCOR.NS", "CROMPTON.NS", 
    "CUMMINSIND.NS", "DIVISLAB.NS", "DIXON.NS", "DLF.NS", "DRREDDY.NS", "EICHERMOT.NS", 
    "GAIL.NS", "GICRE.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRASIM.NS", "HAVELLS.NS", "HCLTECH.NS", 
    "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HAL.NS", 
    "HINDPETRO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ICICIGI.NS", "ICICIPRULI.NS", "ITC.NS", 
    "IOC.NS", "IRCTC.NS", "IREDA.NS", "IRFC.NS", "INDUSINDBK.NS", "NAUKRI.NS", "INFY.NS", "INDIGO.NS", 
    "JSWINFRA.NS", "JSWSTEEL.NS", "JINDALSTEL.NS", "JIOFIN.NS", "KOTAKBANK.NS", "LT.NS", "LTIM.NS", 
    "LUPIN.NS", "M&M.NS", "MARICO.NS", "MARUTI.NS", "MUTHOOTFIN.NS", "NMDC.NS", "NTPC.NS", 
    "NESTLEIND.NS", "ONGC.NS", "PAGEIND.NS", "PIIND.NS", "PIDILITIND.NS", "PFC.NS", 
    "POWERGRID.NS", "PNB.NS", "RECLTD.NS", "RELIANCE.NS", "SBICARD.NS", "SBILIFE.NS", 
    "SBIN.NS", "SHREECEM.NS", "SIEMENS.NS", "SRF.NS", "SUNPHARMA.NS", "TVSMOTOR.NS", 
    "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATAELXSI.NS", "TATAPOWER.NS", "TATASTEEL.NS", 
    "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS", "TRENT.NS", "ULTRACEMCO.NS", "VBL.NS", 
    "VEDL.NS", "WIPRO.NS", "ZOMATO.NS", "ZYDUSLIFE.NS"
]

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram secrets missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram connection error: {e}")

def is_exciting(candle):
    rng = float(candle['High']) - float(candle['Low'])
    if rng == 0:
        return False
    body = abs(float(candle['Close']) - float(candle['Open']))
    return (body / rng) > 0.50

def is_base(candle):
    rng = float(candle['High']) - float(candle['Low'])
    if rng == 0:
        return False
    body = abs(float(candle['Close']) - float(candle['Open']))
    return (body / rng) <= 0.50

def evaluate_gtf_setup(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo", interval="1d")
        if df.empty or len(df) < 50:
            return

        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()

        cmp = float(df['Close'].iloc[-1])
        ema20 = float(df['EMA20'].iloc[-1])
        ema50 = float(df['EMA50'].iloc[-1])
        cross = "Golden Cross (Bullish)" if ema20 > ema50 else "Death Cross (Bearish)"

        for i in range(len(df) - 4, 3, -1):
            leg_in = df.iloc[i-1]
            base = df.iloc[i]
            leg_out = df.iloc[i+1]

            in_open, in_close, in_high, in_low = float(leg_in['Open']), float(leg_in['Close']), float(leg_in['High']), float(leg_in['Low'])
            out_open, out_close, out_high, out_low = float(leg_out['Open']), float(leg_out['Close']), float(leg_out['High']), float(leg_out['Low'])
            base_open, base_close = float(base['Open']), float(base['Close'])
            base_low, base_high = float(base['Low']), float(base['High'])

            # Demand Reversal (DBR)
            if in_close < in_open and is_base(base) and out_close > out_open and is_exciting(leg_out):
                if out_close > in_high:
                    pl = max(base_open, base_close)
                    dl = min(in_low, base_low, out_low)
                    subs_lows = df['Low'].iloc[i+2:].astype(float)
                    if not (subs_lows <= pl).any() and cmp >= pl and ((cmp - pl) / pl) <= 0.015:
                        risk = pl - dl
                        if risk <= 0:
                            continue
                        t1 = pl + (2 * risk)
                        q_beg = int(1000 / risk)
                        q_int = int(1500 / risk)
                        q_pro = int(2000 / risk)

                        lines = [
                            f"<b>🟢 GTF DEMAND ENGINE: {ticker}</b>",
                            "",
                            "<b>I. Zone Anatomy (DBR)</b>",
                            f"• CMP: ₹{cmp:.2f}",
                            f"• Proximal Line (Entry): ₹{pl:.2f}",
                            f"• Distal Line (SL): ₹{dl:.2f}",
                            "• Status: Authentic Origin (Fresh)",
                            "• Closing Concept: Verified ✅",
                            "",
                            "<b>II. Trend & Confluence</b>",
                            f"• 20 EMA: ₹{ema20:.2f}",
                            f"• 50 EMA: ₹{ema50:.2f}",
                            f"• Momentum: {cross}",
                            "",
                            "<b>III. Risk Calibration (₹1 Lakh Capital)</b>",
                            f"• Risk/Share: ₹{risk:.2f}",
                            f"• Beginner (1% / ₹1k): {q_beg} Qty",
                            f"• Intermediate (1.5% / ₹1.5k): {q_int} Qty",
                            f"• Pro (2% / ₹2k): {q_pro} Qty",
                            f"• Target 1 (2:1): ₹{t1:.2f}",
                            "",
                            "<b>IV. Execution Parameters</b>",
                            f"<code>Entry={pl:.2f} | SL={dl:.2f} | Target={t1:.2f}</code>"
                        ]
                        send_telegram_alert("\n".join(lines))
                        break

            # Supply Reversal (RBD)
            if in_close > in_open and is_base(base) and out_close < out_open and is_exciting(leg_out):
                if out_close < in_low:
                    pl = min(base_open, base_close)
                    dl = max(in_high, base_high, out_high)
                    subs_highs = df['High'].iloc[i+2:].astype(float)
                    if not (subs_highs >= pl).any() and cmp <= pl and ((pl - cmp) / pl) <= 0.015:
                        risk = dl - pl
                        if risk <= 0:
                            continue
                        t1 = pl - (2 * risk)
                        q_beg = int(1000 / risk)
                        q_int = int(1500 / risk)
                        q_pro = int(2000 / risk)

                        lines = [
                            f"<b>🔴 GTF SUPPLY ENGINE: {ticker}</b>",
                            "",
                            "<b>I. Zone Anatomy (RBD)</b>",
                            f"• CMP: ₹{cmp:.2f}",
                            f"• Proximal Line (Sell): ₹{pl:.2f}",
                            f"• Distal Line (SL): ₹{dl:.2f}",
                            "• Status: Authentic Origin (Fresh)",
                            "• Closing Concept: Verified ✅",
                            "",
                            "<b>II. Trend & Confluence</b>",
                            f"• 20 EMA: ₹{ema20:.2f}",
                            f"• 50 EMA: ₹{ema50:.2f}",
                            f"• Momentum: {cross}",
                            "",
                            "<b>III. Risk Calibration (₹1 Lakh Capital)</b>",
                            f"• Risk/Share: ₹{risk:.2f}",
                            f"• Beginner (1% / ₹1k): {q_beg} Qty",
                            f"• Intermediate (1.5% / ₹1.5k): {q_int} Qty",
                            f"• Pro (2% / ₹2k): {q_pro} Qty",
                            f"• Target 1 (2:1): ₹{t1:.2f}",
                            "",
                            "<b>IV. Execution Parameters</b>",
                            f"<code>Entry={pl:.2f} | SL={dl:.2f} | Target={t1:.2f}</code>"
                        ]
                        send_telegram_alert("\n".join(lines))
                        break
    except Exception as e:
        print(f"Error checking {ticker}: {e}")

if __name__ == "__main__":
    for symbol in WATCHLIST:
        evaluate_gtf_setup(symbol)
