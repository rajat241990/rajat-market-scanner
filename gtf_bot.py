import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf

# ==========================================
# CONFIGURATION & TELEGRAM SETUP
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RISK_PER_TRADE = 1000  # Default risk in INR (1% of 1 Lakh capital)

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
    """Dispatches HTML-formatted alerts to Telegram."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Communication Error: {e}")

# ==========================================
# MICROSTRUCTURE CANDLE CLASSIFICATION
# ==========================================
def classify_candles(df):
    """
    Vectorized classification based on the 50% Body-to-Range rule.
    """
    df = df.copy()
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Range'] = np.where(df['Range'] == 0, 0.0001, df['Range'])
    
    df['Ratio'] = df['Body'] / df['Range']
    df['Is_Exciting'] = df['Ratio'] > 0.50
    df['Is_Base'] = df['Ratio'] <= 0.50
    df['Color'] = np.where(df['Close'] > df['Open'], 'Green', 'Red')
    return df

# ==========================================
# GTF COMPLIANT ZONE SCANNER (SOP v4.2)
# ==========================================
def detect_zones(df, zone_type="Demand"):
    """
    Detects authentic Supply/Demand zones strictly below (Demand) or above (Supply) CMP.
    Applies Exceptional Marking, Closing Concept, and GTF 7-Point Quality Scoring.
    """
    zones = []
    n = len(df)
    cmp = float(df['Close'].iloc[-1])
    
    # Iterate backwards to find historical zones relative to CMP
    for i in range(n - 2, 6, -1):
        leg_out = df.iloc[i+1]
        
        # 1. Leg-Out Check
        if not leg_out['Is_Exciting']:
            continue
        if zone_type == "Demand" and leg_out['Color'] != 'Green':
            continue
        if zone_type == "Supply" and leg_out['Color'] != 'Red':
            continue

        # 2. Base Candle Aggregation (1 to 5 bases, 1-3 optimal)
        base_candles = []
        base_indices = []
        for j in range(i, max(0, i - 6), -1):
            if df.iloc[j]['Is_Base']:
                base_candles.append(df.iloc[j])
                base_indices.append(j)
            else:
                break
                
        if len(base_candles) == 0 or len(base_candles) > 5:
            continue
            
        # 3. Leg-In Validation
        leg_in_idx = base_indices[-1] - 1
        if leg_in_idx < 0:
            continue
        leg_in = df.iloc[leg_in_idx]
        
        if not leg_in['Is_Exciting']:
            continue

        # 4. Closing Concept Verification
        leg_in_body_high = max(leg_in['Open'], leg_in['Close'])
        leg_in_body_low = min(leg_in['Open'], leg_in['Close'])
        
        if zone_type == "Demand" and leg_out['Close'] <= leg_in_body_high:
            continue
        if zone_type == "Supply" and leg_out['Close'] >= leg_in_body_low:
            continue

        # Pattern Type
        if zone_type == "Demand":
            pattern = "DBR" if leg_in['Color'] == 'Red' else "RBR"
        else:
            pattern = "RBD" if leg_in['Color'] == 'Green' else "DBD"

        # 5. Boundary Line Marking Standards
        base_df = pd.DataFrame(base_candles)
        if zone_type == "Demand":
            # Proximal: Highest body of base candles
            pl = base_df[['Open', 'Close']].max().max()
            
            # Demand MUST be strictly below CMP
            if pl >= cmp:
                continue
                
            base_min_wick = base_df['Low'].min()
            out_min_wick = leg_out['Low']
            in_min_wick = leg_in['Low']
            
            # Exceptional Marking: Reversal vs Continuation
            if pattern == "DBR":
                dl = min(in_min_wick, base_min_wick, out_min_wick)
            else:
                dl = min(base_min_wick, out_min_wick)
        else:
            # Proximal: Lowest body of base candles
            pl = base_df[['Open', 'Close']].min().min()
            
            # Supply MUST be strictly above CMP
            if pl <= cmp:
                continue
                
            base_max_wick = base_df['High'].max()
            out_max_wick = leg_out['High']
            in_max_wick = leg_in['High']
            
            # Exceptional Marking: Reversal vs Continuation
            if pattern == "RBD":
                dl = max(in_max_wick, base_max_wick, out_max_wick)
            else:
                dl = max(base_max_wick, out_max_wick)

        # 6. Freshness and Retest Verification
        post_zone_df = df.iloc[i+2:]
        is_fresh = True
        is_breached = False

        if not post_zone_df.empty:
            if zone_type == "Demand":
                if (post_zone_df['Low'] < dl).any():
                    is_breached = True
                elif (post_zone_df['Low'] <= pl).any():
                    is_fresh = False
            else:
                if (post_zone_df['High'] > dl).any():
                    is_breached = True
                elif (post_zone_df['High'] >= pl).any():
                    is_fresh = False

        if is_breached or not is_fresh:
            continue

        # 7. GTF Quality Scoring (7-Point Base)
        score = 3.0  # Freshness
        score += 2.0 if (len(df) > i+2 and df.iloc[i+2]['Is_Exciting']) else 1.0  # Leg-out power
        score += 2.0 if len(base_candles) <= 3 else 1.0  # Time at base
        
        zones.append({
            'Pattern': pattern,
            'PL': round(float(pl), 2),
            'DL': round(float(dl), 2),
            'Base_Count': len(base_candles),
            'Score': score,
            'Index': i
        })
        break

    return zones[0] if zones else None

# ==========================================
# MULTI-TIMEFRAME ANALYSIS (MTFA)
# ==========================================
def evaluate_mtfa(ticker):
    """
    Orchestrates MTFA workflow under GTF SOP v4.2 rules.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # 1. HTF Curve Analysis (Monthly)
        df_htf = stock.history(period="5y", interval="1mo")
        if df_htf.empty or len(df_htf) < 5: return
        df_htf = classify_candles(df_htf)
        
        htf_demand = detect_zones(df_htf, "Demand")
        htf_supply = detect_zones(df_htf, "Supply")
        
        curve_loc = "Equilibrium (Follow Trend)"
        cmp = float(df_htf['Close'].iloc[-1])
        
        if htf_demand and htf_supply:
            dem_pl = htf_demand['PL']
            sup_pl = htf_supply['PL']
            if sup_pl > dem_pl:
                spread = sup_pl - dem_pl
                if cmp <= dem_pl + (spread / 3):
                    curve_loc = "Low (Buy Preferred)"
                elif cmp >= sup_pl - (spread / 3):
                    curve_loc = "High (Sell Preferred)"

        # 2. ITF Trend Analysis (Weekly)
        df_itf = stock.history(period="2y", interval="1wk")
        if df_itf.empty or len(df_itf) < 20: return
        df_itf['EMA20'] = df_itf['Close'].ewm(span=20, adjust=False).mean()
        
        itf_close = float(df_itf['Close'].iloc[-1])
        itf_ema20 = float(df_itf['EMA20'].iloc[-1])
        itf_trend = "Bullish" if itf_close > itf_ema20 else "Bearish"

        # 3. LTF Execution Analysis (Daily)
        df_ltf = stock.history(period="1y", interval="1d")
        if df_ltf.empty or len(df_ltf) < 50: return
        df_ltf = classify_candles(df_ltf)
        
        ltf_demand = detect_zones(df_ltf, "Demand")
        ltf_supply = detect_zones(df_ltf, "Supply")
        
        # Execution Evaluation
        if ltf_demand and curve_loc != "High (Sell Preferred)" and itf_trend == "Bullish":
            pl, dl = ltf_demand['PL'], ltf_demand['DL']
            risk = round(pl - dl, 2)
            if risk > 0 and ltf_demand['Score'] >= 5.0:
                qty = int(RISK_PER_TRADE / risk)
                entry = round(pl + (risk * 0.05), 2)
                sl = round(dl - (risk * 0.05), 2)
                target = round(entry + (2 * (entry - sl)), 2)
                
                msg = (
                    f"🟢 <b>GTF MTFA DEMAND ALERT ({ltf_demand['Pattern']})</b>: {ticker}\n\n"
                    f"<b>I. MULTI-TIMEFRAME ALIGNMENT</b>\n"
                    f"• HTF Curve: {curve_loc}\n"
                    f"• ITF Trend: {itf_trend} (Relative to 20 EMA)\n\n"
                    f"<b>II. LTF EXECUTION ZONE</b>\n"
                    f"• CMP: Rs {round(cmp, 2)}\n"
                    f"• Score: {ltf_demand['Score']}/7.0\n"
                    f"• Entry: Rs {entry}\n"
                    f"• Stop Loss: Rs {sl}\n"
                    f"• Base Candles: {ltf_demand['Base_Count']}\n\n"
                    f"<b>III. POSITION SIZING (Risk Rs {RISK_PER_TRADE})</b>\n"
                    f"• Target (2:1): Rs {target}\n"
                    f"• Quantity: {qty} Shares"
                )
                send_telegram_alert(msg)

        if ltf_supply and curve_loc != "Low (Buy Preferred)" and itf_trend == "Bearish":
            pl, dl = ltf_supply['PL'], ltf_supply['DL']
            risk = round(dl - pl, 2)
            if risk > 0 and ltf_supply['Score'] >= 5.0:
                qty = int(RISK_PER_TRADE / risk)
                entry = round(pl - (risk * 0.05), 2)
                sl = round(dl + (risk * 0.05), 2)
                target = round(entry - (2 * (sl - entry)), 2)
                
                msg = (
                    f"🔴 <b>GTF MTFA SUPPLY ALERT ({ltf_supply['Pattern']})</b>: {ticker}\n\n"
                    f"<b>I. MULTI-TIMEFRAME ALIGNMENT</b>\n"
                    f"• HTF Curve: {curve_loc}\n"
                    f"• ITF Trend: {itf_trend} (Relative to 20 EMA)\n\n"
                    f"<b>II. LTF EXECUTION ZONE</b>\n"
                    f"• CMP: Rs {round(cmp, 2)}\n"
                    f"• Score: {ltf_supply['Score']}/7.0\n"
                    f"• Entry: Rs {entry}\n"
                    f"• Stop Loss: Rs {sl}\n"
                    f"• Base Candles: {ltf_supply['Base_Count']}\n\n"
                    f"<b>III. POSITION SIZING (Risk Rs {RISK_PER_TRADE})</b>\n"
                    f"• Target (2:1): Rs {target}\n"
                    f"• Quantity: {qty} Shares"
                )
                send_telegram_alert(msg)

    except Exception:
        pass

if __name__ == "__main__":
    for symbol in WATCHLIST:
        evaluate_mtfa(symbol)
