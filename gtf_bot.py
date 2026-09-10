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
        return
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

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

def get_htf_zones(df, cmp):
    sup_pl, dem_pl = None, None
    try:
        for i in range(len(df) - 2, 1, -1):
            base, leg_out = df.iloc[i], df.iloc[i+1]
            out_c, out_o = float(leg_out['Close']), float(leg_out['Open'])
            b_c, b_o = float(base['Close']), float(base['Open'])
            
            if sup_pl is None and out_c < out_o and is_exciting(leg_out) and is_base(base):
                pl = min(b_c, b_o)
                if pl > cmp: sup_pl = pl
                
            if dem_pl is None and out_c > out_o and is_exciting(leg_out) and is_base(base):
                pl = max(b_c, b_o)
                if pl < cmp: dem_pl = pl
                
            if sup_pl and dem_pl: break
    except:
        pass
    return sup_pl, dem_pl

def evaluate_gtf_setup(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        # 1. HTF (Monthly) - 5 Years Data for Curve Location
        df_htf = stock.history(period="5y", interval="1mo")
        curve_loc = "Calculating..."
        htf_sup_str, htf_dem_str = "N/A", "N/A"
        if not df_htf.empty and len(df_htf) > 5:
            cmp_htf = float(df_htf['Close'].iloc[-1])
            htf_sup, htf_dem = get_htf_zones(df_htf, cmp_htf)
            if htf_sup: htf_sup_str = str(round(htf_sup, 2))
            if htf_dem: htf_dem_str = str(round(htf_dem, 2))
            
            if htf_sup and htf_dem and htf_sup > htf_dem:
                spread = htf_sup - htf_dem
                if cmp_htf <= htf_dem + (spread/3):
                    curve_loc = "Low (Buy Preferred)"
                elif cmp_htf >= htf_sup - (spread/3):
                    curve_loc = "High (Sell Preferred)"
                else:
                    curve_loc = "Equilibrium (Follow Trend)"

        # 2. ITF (Weekly) - 2 Years Data for Trend
        df_itf = stock.history(period="2y", interval="1wk")
        itf_trend = "Unknown"
        if not df_itf.empty and len(df_itf) > 20:
            df_itf['EMA20'] = df_itf['Close'].ewm(span=20, adjust=False).mean()
            if float(df_itf['Close'].iloc[-1]) > float(df_itf['EMA20'].iloc[-1]):
                itf_trend = "Bullish (Above 20 EMA)"
            else:
                itf_trend = "Bearish (Below 20 EMA)"

        # ... existing code ...
            # LTF Supply Reversal (RBD)
            if in_close > in_open and is_base(base) and out_close < out_open and is_exciting(leg_out):
                if out_close < in_low:
                    pl = min(base_open, base_close)
                    dl = max(in_high, base_high, out_high)
                    subs_highs = df['High'].iloc[i+2:].astype(float)
                    if not (subs_highs >= pl).any() and cmp <= pl and ((pl - cmp) / pl) <= 0.015:
                        risk = dl - pl
                        if risk <= 0: continue
                        t1 = pl - (2 * risk)
                        q_beg = int(1000 / risk)
                        q_pro = int(2000 / risk)

                        msg = (
                            "🔴 GTF MTFA SUPPLY ALERT: " + ticker + "\n\n"
                            "I. MULTI-TIMEFRAME ALIGNMENT\n"
                            "• HTF Curve: " + curve_loc + "\n"
                            "• HTF Supply: Rs " + htf_sup_str + "\n"
                            "• HTF Demand: Rs " + htf_dem_str + "\n"
                            "• ITF Trend: " + itf_trend + "\n\n"
                            "II. LTF EXECUTION ZONE\n"
                            "• CMP: Rs " + str(round(cmp, 2)) + "\n"
                            "• Entry (PL): Rs " + str(round(pl, 2)) + "\n"
                            "• Stop Loss (DL): Rs " + str(round(dl, 2)) + "\n\n"
                            "III. POSITION SIZING (Rs 1 Lakh)\n"
                            "• Target 1: Rs " + str(round(t1, 2)) + "\n"
                            "• Beginner (1%): " + str(q_beg) + " Qty\n"
                            "• Pro (2%): " + str(q_pro) + " Qty"
                        )
                        send_telegram_alert(msg)
                        break

            # LTF Demand Continuous (RBR)
            if in_close > in_open and is_base(base) and out_close > out_open and is_exciting(leg_out):
                if out_close > in_high:
                    pl = max(base_open, base_close)
                    # Exceptional Marking for Continuous: Ignore leg-in wick
                    dl = min(base_low, out_low) 
                    subs_lows = df['Low'].iloc[i+2:].astype(float)
                    if not (subs_lows <= pl).any() and cmp >= pl and ((cmp - pl) / pl) <= 0.015:
                        risk = pl - dl
                        if risk <= 0: continue
                        t1 = pl + (2 * risk)
                        q_beg = int(1000 / risk)
                        q_pro = int(2000 / risk)

                        msg = (
                            "🟢 GTF MTFA DEMAND ALERT (RBR): " + ticker + "\n\n"
                            "I. MULTI-TIMEFRAME ALIGNMENT\n"
                            "• HTF Curve: " + curve_loc + "\n"
                            "• HTF Supply: Rs " + htf_sup_str + "\n"
                            "• HTF Demand: Rs " + htf_dem_str + "\n"
                            "• ITF Trend: " + itf_trend + "\n\n"
                            "II. LTF EXECUTION ZONE\n"
                            "• CMP: Rs " + str(round(cmp, 2)) + "\n"
                            "• Entry (PL): Rs " + str(round(pl, 2)) + "\n"
                            "• Stop Loss (DL): Rs " + str(round(dl, 2)) + "\n\n"
                            "III. POSITION SIZING (Rs 1 Lakh)\n"
                            "• Target 1: Rs " + str(round(t1, 2)) + "\n"
                            "• Beginner (1%): " + str(q_beg) + " Qty\n"
                            "• Pro (2%): " + str(q_pro) + " Qty"
                        )
                        send_telegram_alert(msg)
                        break

            # LTF Supply Continuous (DBD)
            if in_close < in_open and is_base(base) and out_close < out_open and is_exciting(leg_out):
                if out_close < in_low:
                    pl = min(base_open, base_close)
                    # Exceptional Marking for Continuous: Ignore leg-in wick
                    dl = max(base_high, out_high)
                    subs_highs = df['High'].iloc[i+2:].astype(float)
                    if not (subs_highs >= pl).any() and cmp <= pl and ((pl - cmp) / pl) <= 0.015:
                        risk = dl - pl
                        if risk <= 0: continue
                        t1 = pl - (2 * risk)
                        q_beg = int(1000 / risk)
                        q_pro = int(2000 / risk)

                        msg = (
                            "🔴 GTF MTFA SUPPLY ALERT (DBD): " + ticker + "\n\n"
                            "I. MULTI-TIMEFRAME ALIGNMENT\n"
                            "• HTF Curve: " + curve_loc + "\n"
                            "• HTF Supply: Rs " + htf_sup_str + "\n"
                            "• HTF Demand: Rs " + htf_dem_str + "\n"
                            "• ITF Trend: " + itf_trend + "\n\n"
                            "II. LTF EXECUTION ZONE\n"
                            "• CMP: Rs " + str(round(cmp, 2)) + "\n"
                            "• Entry (PL): Rs " + str(round(pl, 2)) + "\n"
                            "• Stop Loss (DL): Rs " + str(round(dl, 2)) + "\n\n"
                            "III. POSITION SIZING (Rs 1 Lakh)\n"
                            "• Target 1: Rs " + str(round(t1, 2)) + "\n"
                            "• Beginner (1%): " + str(q_beg) + " Qty\n"
                            "• Pro (2%): " + str(q_pro) + " Qty"
                        )
                        send_telegram_alert(msg)
                        break
    except Exception as e:
# ... existing code ...
```

### Key Additions Explained:
1. **RBR & DBD Logic:** The code now properly looks for Rally (`in_close > in_open`) - Base - Rally (`out_close > out_open`) and Drop - Base - Drop combinations.
2. **Proper Distal Lines:** Notice that for `dl` in both RBR and DBD blocks, `in_low` and `in_high` are completely omitted from the `min()` and `max()` functions, satisfying the GTF exceptional marking rules.
        # 3. LTF (Daily) - 1 Year Data for Execution Zone
        df = stock.history(period="1y", interval="1d")
        if df.empty or len(df) < 50:
            return

        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()

        cmp = float(df['Close'].iloc[-1])
        ema20 = float(df['EMA20'].iloc[-1])
        ema50 = float(df['EMA50'].iloc[-1])
        cross = "Golden Cross" if ema20 > ema50 else "Death Cross"

        for i in range(len(df) - 4, 3, -1):
            leg_in = df.iloc[i-1]
            base = df.iloc[i]
            leg_out = df.iloc[i+1]

            in_open, in_close, in_high, in_low = float(leg_in['Open']), float(leg_in['Close']), float(leg_in['High']), float(leg_in['Low'])
            out_open, out_close, out_high, out_low = float(leg_out['Open']), float(leg_out['Close']), float(leg_out['High']), float(leg_out['Low'])
            base_open, base_close = float(base['Open']), float(base['Close'])
            base_low, base_high = float(base['Low']), float(base['High'])

            # LTF Demand Reversal (DBR)
            if in_close < in_open and is_base(base) and out_close > out_open and is_exciting(leg_out):
                if out_close > in_high:
                    pl = max(base_open, base_close)
                    dl = min(in_low, base_low, out_low)
                    subs_lows = df['Low'].iloc[i+2:].astype(float)
                    if not (subs_lows <= pl).any() and cmp >= pl and ((cmp - pl) / pl) <= 0.015:
                        risk = pl - dl
                        if risk <= 0: continue
                        t1 = pl + (2 * risk)
                        q_beg = int(1000 / risk)
                        q_pro = int(2000 / risk)

                        msg = (
                            "🟢 GTF MTFA DEMAND ALERT: " + ticker + "\n\n"
                            "I. MULTI-TIMEFRAME ALIGNMENT\n"
                            "• HTF Curve: " + curve_loc + "\n"
                            "• HTF Supply: Rs " + htf_sup_str + "\n"
                            "• HTF Demand: Rs " + htf_dem_str + "\n"
                            "• ITF Trend: " + itf_trend + "\n\n"
                            "II. LTF EXECUTION ZONE\n"
                            "• CMP: Rs " + str(round(cmp, 2)) + "\n"
                            "• Entry (PL): Rs " + str(round(pl, 2)) + "\n"
                            "• Stop Loss (DL): Rs " + str(round(dl, 2)) + "\n\n"
                            "III. POSITION SIZING (Rs 1 Lakh)\n"
                            "• Target 1: Rs " + str(round(t1, 2)) + "\n"
                            "• Beginner (1%): " + str(q_beg) + " Qty\n"
                            "• Pro (2%): " + str(q_pro) + " Qty"
                        )
                        send_telegram_alert(msg)
                        break

            # LTF Supply Reversal (RBD)
            if in_close > in_open and is_base(base) and out_close < out_open and is_exciting(leg_out):
                if out_close < in_low:
                    pl = min(base_open, base_close)
                    dl = max(in_high, base_high, out_high)
                    subs_highs = df['High'].iloc[i+2:].astype(float)
                    if not (subs_highs >= pl).any() and cmp <= pl and ((pl - cmp) / pl) <= 0.015:
                        risk = dl - pl
                        if risk <= 0: continue
                        t1 = pl - (2 * risk)
                        q_beg = int(1000 / risk)
                        q_pro = int(2000 / risk)

                        msg = (
                            "🔴 GTF MTFA SUPPLY ALERT: " + ticker + "\n\n"
                            "I. MULTI-TIMEFRAME ALIGNMENT\n"
                            "• HTF Curve: " + curve_loc + "\n"
                            "• HTF Supply: Rs " + htf_sup_str + "\n"
                            "• HTF Demand: Rs " + htf_dem_str + "\n"
                            "• ITF Trend: " + itf_trend + "\n\n"
                            "II. LTF EXECUTION ZONE\n"
                            "• CMP: Rs " + str(round(cmp, 2)) + "\n"
                            "• Entry (PL): Rs " + str(round(pl, 2)) + "\n"
                            "• Stop Loss (DL): Rs " + str(round(dl, 2)) + "\n\n"
                            "III. POSITION SIZING (Rs 1 Lakh)\n"
                            "• Target 1: Rs " + str(round(t1, 2)) + "\n"
                            "• Beginner (1%): " + str(q_beg) + " Qty\n"
                            "• Pro (2%): " + str(q_pro) + " Qty"
                        )
                        send_telegram_alert(msg)
                        break
    except Exception as e:
        pass

if __name__ == "__main__":
    for symbol in WATCHLIST:
        evaluate_gtf_setup(symbol)
