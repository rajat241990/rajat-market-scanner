 import os
import requests
import yfinance as yf

# Load tokens from GitHub Secrets
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
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    requests.post(url, json=payload)

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

def calculate_ema(df, period):
    return df['Close'].ewm(span=period, adjust=False).mean()

def evaluate_gtf_setup(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo", interval="1d")
        if df.empty or len(df) < 50: return

        # Calculate EMAs for Trend Confluence
        df['EMA20'] = calculate_ema(df, 20)
        df['EMA50'] = calculate_ema(df, 50)
        
        cmp = float(df['Close'].iloc[-1])
        ema20 = float(df['EMA20'].iloc[-1])
        ema50 = float(df['EMA50'].iloc[-1])
        
        cross_status = "Golden Cross 🟢" if ema20 > ema50 else "Death Cross 🔴"
        
        for i in range(len(df) - 4, 3, -1):
            leg_in = df.iloc[i-1]
            base = df.iloc[i]
            leg_out = df.iloc[i+1]

            in_open, in_close, in_high, in_low = float(leg_in['Open']), float(leg_in['Close']), float(leg_in['High']), float(leg_in['Low'])
            out_open, out_close, out_high, out_low = float(leg_out['Open']), float(leg_out['Close']), float(leg_out['High']), float(leg_out['Low'])
            base_open, base_close, base_high, base_low = float(base['Open']), float(base['Close']), float(base['High']), float(base['Low'])
            
            # 1. Drop-Base-Rally (Demand Reversal)
            if in_close < in_open and is_base(base) and out_close > out_open and is_exciting(leg_out):
                if out_close > in_high: # Closing Concept
                    pl = max(base_open, base_close)
                    dl = min(in_low, base_low, out_low)
                    
                    subs_lows = df['Low'].iloc[i+2:].astype(float)
                    if not (subs_lows <= pl).any() and cmp >= pl and ((cmp - pl) / pl) <= 0.015:
                        risk = pl - dl
                        if risk == 0: continue
                        t1 = pl + (2 * risk)
                        
                        # Position Sizing based on 1 Lakh Capital rules
                        qty_beg = int(1000 / risk)
                        qty_int = int(1500 / risk)
                        qty_pro = int(2000 / risk)
                        
                        msg = f"""<b>🟢 GTF DEMAND ENGINE: {ticker}</b>

<b>I. Zone Anatomy (DBR)</b>
• <b>CMP:</b> ₹{cmp:.2f}
• <b>Proximal Line (Entry):</b> ₹{pl:.2f}
• <b>Distal Line (SL):</b> ₹{dl:.2f}
• <b>Status:</b> Authentic Origin (Fresh)
• <b>Closing Concept:</b> Verified ✅

<b>II. Trend & Confluence</b>
• <b>EMA 20 Status:</b> ₹{ema20:.2f}
• <b>Momentum:</b> {cross_status}

<b>III. Risk Calibration (₹1 Lakh)</b>
• <b>Risk/Share:</b> ₹{risk:.2f}
• <b>Beginner (1% / ₹1000):</b> {qty_beg} Qty
• <b>Intermed (1.5% / ₹1500):</b> {qty_int} Qty
• <b>Pro (2% / ₹2000):</b> {qty_pro} Qty
• <b>Target 1 (2:1):</b> ₹{t1:.2f}

<b>IV. TradingView Pine Script</b>
<code>//@version=5
indicator("GTF Setup", overlay=true)
plot({pl:.2f}, "PL", color=color.blue, linewidth=2)
plot({dl:.2f}, "DL", color=color.red, linewidth=2)
plot({t1:.2f}, "Target", color=color.green, linewidth=2)
var box dz = box.new(bar_index-10, {pl:.2f}, bar_index+15, {dl:.2f}, bgcolor=color.new(color.green, 85), border_color=color.green)</code>"""
                        send_telegram_alert(msg)
                        break

            # 2. Rally-Base-Drop (Supply Reversal)
            if in_close > in_open and is_base(base) and out_close < out_open and is_exciting(leg_out):
                if out_close < in_low: # Closing Concept
                    pl = min(base_open, base_close)
                    dl = max(in_high, base_high, out_high)
                    
                    subs_highs = df['High'].iloc[i+2:].astype(float)
                    if not (subs_highs >= pl).any() and cmp <= pl and ((pl - cmp) / pl) <= 0.015:
                        risk = dl - pl
                        if risk == 0: continue
                        t1 = pl - (2 * risk)
                        
                        # Position Sizing based on 1 Lakh Capital rules
                        qty_beg = int(1000 / risk)
                        qty_int = int(1500 / risk)
                        qty_pro = int(2000 / risk)
                        
                        msg = f"""<b>🔴 GTF SUPPLY ENGINE: {ticker}</b>

<b>I. Zone Anatomy (RBD)</b>
• <b>CMP:</b> ₹{cmp:.2f}
• <b>Proximal Line (Sell):</b> ₹{pl:.2f}
• <b>Distal Line (SL):</b> ₹{dl:.2f}
• <b>Status:</b> Authentic Origin (Fresh)
• <b>Closing Concept:</b> Verified ✅

<b>II. Trend & Confluence</b>
• <b>EMA 20 Status:</b> ₹{ema20:.2f}
• <b>Momentum:</b> {cross_status}

<b>III. Risk Calibration (₹1 Lakh)</b>
• <b>Risk/Share:</b> ₹{risk:.2f}
• <b>Beginner (1% / ₹1000):</b> {qty_beg} Qty
• <b>Intermed (1.5% / ₹1500):</b> {qty_int} Qty
• <b>Pro (2% / ₹2000):</b> {qty_pro} Qty
• <b>Target 1 (2:1):</b> ₹{t1:.2f}

<b>IV. TradingView Pine Script</b>
<code>//@version=5
indicator("GTF Setup", overlay=true)
plot({pl:.2f}, "PL", color=color.blue, linewidth=2)
plot({dl:.2f}, "DL", color=color.red, linewidth=2)
plot({t1:.2f}, "Target", color=color.green, linewidth=2)
var box sz = box.new(bar_index-10, {dl:.2f}, bar_index+15, {pl:.2f}, bgcolor=color.new(color.red, 85), border_color=color.red)</code>"""
                        send_telegram_alert(msg)
                        break
    except Exception as e:
        pass

if __name__ == "__main__":
    for symbol in WATCHLIST:
        evaluate_gtf_setup(symbol)
