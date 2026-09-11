import os
import requests
import numpy as np
import pandas as pd
from datetime import datetime
from tvDatafeed import TvDatafeed, Interval

# ==========================================
# CONFIGURATION & TELEGRAM SETUP
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RISK_PER_TRADE = 1000  # Default risk in INR (1% of 1 Lakh capital)

# Core NSE Watchlist (High Liquidity)
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

# Initialize TradingView Datafeed (Anonymous login is sufficient for basic data)
tv = TvDatafeed()

def send_telegram_alert(message):
    """Dispatches HTML-formatted alerts to Telegram."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(message) # Fallback to console if credentials missing
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Communication Error: {e}")

# ==========================================
# MICROSTRUCTURE CANDLE CLASSIFICATION
# ==========================================
def classify_candles(df):
    """
    Vectorized classification of Exciting vs. Base candles.
    Calculates Range, Body, and proportional ratios to determine order flow imbalances.
    """
    df = df.copy()
    df['Range'] = df['high'] - df['low']
    df['Body'] = abs(df['close'] - df['open'])
    
    # Handle zero range to avoid division by zero errors in illiquid assets
    df['Range'] = np.where(df['Range'] == 0, 0.0001, df['Range'])
    
    df['Ratio'] = df['Body'] / df['Range']
    df['Is_Exciting'] = df['Ratio'] > 0.50
    df['Is_Base'] = df['Ratio'] <= 0.50
    df['Color'] = np.where(df['close'] > df['open'], 'Green', 'Red')
    return df

# ==========================================
# DYNAMIC ZONE SCANNING ENGINE
# ==========================================
def detect_zones(df, zone_type="Demand"):
    """
    Scans the dataframe for institutional Supply/Demand zones using dynamic base counting 
    (1 to 6 base candles) and applies Exceptional DL marking and Closing Concept validation.
    """
    zones = []
    n = len(df)
    
    # Iterate backwards to prioritize the most recently formed fresh zones
    for i in range(n - 2, 6, -1):
        leg_out = df.iloc[i+1]
        
        # Condition 1: Valid Leg-out based on zone type requirements
        if not leg_out['Is_Exciting']:
            continue
            
        if zone_type == "Demand" and leg_out['Color'] != 'Green':
            continue
        if zone_type == "Supply" and leg_out['Color'] != 'Red':
            continue

        # Condition 2: Trace back to find 1 to 6 Base candles representing institutional accumulation
        base_candles = []
        base_idx = []
        for j in range(i, max(0, i - 6), -1):
            if df.iloc[j]['Is_Base']:
                base_candles.append(df.iloc[j])
                base_idx.append(j)
            else:
                break
                
        if len(base_candles) == 0 or len(base_candles) > 6:
            continue # Invalid base structure
            
        # Condition 3: Check for the Leg-In preceding the bases
        leg_in_idx = base_idx[-1] - 1
        leg_in = df.iloc[leg_in_idx]
        
        if not leg_in['Is_Exciting']:
            continue

        # Condition 4: Closing Concept (Achievement of liquidity consumption)
        if zone_type == "Demand" and leg_out['close'] <= leg_in['high']:
            continue # Failed to absorb resting sellers
        if zone_type == "Supply" and leg_out['close'] >= leg_in['low']:
            continue # Failed to absorb resting buyers

        # Determine Specific Topological Pattern
        pattern = ""
        if zone_type == "Demand":
            pattern = "RBR" if leg_in['Color'] == 'Green' else "DBR"
        else:
            pattern = "DBD" if leg_in['Color'] == 'Red' else "RBD"

        # Calculate Proximal Line (PL) from base bodies
        base_df = pd.DataFrame(base_candles)
        if zone_type == "Demand":
            pl = base_df[['open', 'close']].max().max()
        else:
            pl = base_df[['open', 'close']].min().min()

        # Calculate Distal Line (DL) with Exceptional Marking Logic
        dl = 0.0
        if zone_type == "Demand":
            base_lowest_wick = base_df['low'].min()
            out_lowest_wick = leg_out['low']
            in_lowest_wick = leg_in['low']
            
            if pattern == "DBR": # Reversal
                dl = min(in_lowest_wick, base_lowest_wick, out_lowest_wick)
            else: # RBR (Ignore leg-in for continuous patterns)
                dl = min(base_lowest_wick, out_lowest_wick)
                
        elif zone_type == "Supply":
            base_highest_wick = base_df['high'].max()
            out_highest_wick = leg_out['high']
            in_highest_wick = leg_in['high']
            
            if pattern == "RBD": # Reversal
                dl = max(in_highest_wick, base_highest_wick, out_highest_wick)
            else: # DBD (Ignore leg-in for continuous patterns)
                dl = max(base_highest_wick, out_highest_wick)

        # Freshness Check: Has price breached the PL since creation?
        post_zone_df = df.iloc[i+2:]
        if not post_zone_df.empty:
            if zone_type == "Demand" and (post_zone_df['low'] <= pl).any():
                continue # Zone tested or broken; discard
            if zone_type == "Supply" and (post_zone_df['high'] >= pl).any():
                continue # Zone tested or broken; discard

        # Zone is authentic, structurally sound, and fresh.
        zones.append({
            'Pattern': pattern,
            'PL': round(pl, 2),
            'DL': round(dl, 2),
            'Base_Count': len(base_candles),
            'Index': i
        })
        
        # To avoid overlapping zones in proximity, we break after finding the most recent valid zone
        break 

    return zones[0] if zones else None

# ==========================================
# MULTI-TIMEFRAME ANALYSIS (MTFA) COORDINATOR
# ==========================================
def evaluate_mtfa(ticker, exchange='NSE'):
    """
    Fetches Monthly (HTF), Weekly (ITF), and Daily (LTF) data via tvdatafeed.
    Evaluates Curve location, moving average Trend, and LTF Execution zones.
    """
    print(f"Executing MTFA scan for {ticker}...")
    try:
        # 1. HTF Curve Analysis (Monthly - 120 bars = 10 Years)
        df_htf = tv.get_hist(symbol=ticker, exchange=exchange, interval=Interval.in_monthly, n_bars=120)
        if df_htf is None or df_htf.empty: return
        df_htf = classify_candles(df_htf)
        
        htf_demand = detect_zones(df_htf, "Demand")
        htf_supply = detect_zones(df_htf, "Supply")
        
        curve_loc = "Equilibrium"
        cmp = float(df_htf['close'].iloc[-1])
        
        if htf_demand and htf_supply:
            dem_pl = htf_demand['PL']
            sup_pl = htf_supply['PL']
            if sup_pl > dem_pl:
                spread = sup_pl - dem_pl
                if cmp <= dem_pl + (spread / 3):
                    curve_loc = "Low (Buy Preferred)"
                elif cmp >= sup_pl - (spread / 3):
                    curve_loc = "High (Sell Preferred)"

        # 2. ITF Trend Analysis (Weekly - 150 bars = ~3 Years)
        df_itf = tv.get_hist(symbol=ticker, exchange=exchange, interval=Interval.in_weekly, n_bars=150)
        df_itf['EMA20'] = df_itf['close'].ewm(span=20, adjust=False).mean()
        itf_close = float(df_itf['close'].iloc[-1])
        itf_ema20 = float(df_itf['EMA20'].iloc[-1])
        
        itf_trend = "Bullish" if itf_close > itf_ema20 else "Bearish"

        # 3. LTF Execution Analysis (Daily - 300 bars = ~1 Year)
        df_ltf = tv.get_hist(symbol=ticker, exchange=exchange, interval=Interval.in_daily, n_bars=300)
        df_ltf = classify_candles(df_ltf)
        
        ltf_demand = detect_zones(df_ltf, "Demand")
        ltf_supply = detect_zones(df_ltf, "Supply")
        
        # Demand Execution Logic: Favorable Curve + Favorable Trend
        if ltf_demand and curve_loc != "High (Sell Preferred)" and itf_trend == "Bullish":
            pl, dl = ltf_demand['PL'], ltf_demand['DL']
            # Proximity check: Alert only if CMP is within 2% of the Proximal Line
            if pl <= cmp <= pl * 1.02:
                risk = pl - dl
                if risk > 0:
                    qty = int(RISK_PER_TRADE / risk)
                    target = pl + (2 * risk) # 2:1 Reward to Risk Ratio
                    
                    msg = (
                        f"🟢 <b>GTF MTFA DEMAND ALERT ({ltf_demand['Pattern']})</b>: {ticker}\n\n"
                        f"<b>I. MULTI-TIMEFRAME ALIGNMENT</b>\n"
                        f"• HTF Curve: {curve_loc}\n"
                        f"• ITF Trend: {itf_trend} (Above 20 EMA)\n\n"
                        f"<b>II. LTF EXECUTION ZONE</b>\n"
                        f"• CMP: Rs {round(cmp, 2)}\n"
                        f"• Entry (PL): Rs {pl}\n"
                        f"• Stop Loss (DL): Rs {dl}\n"
                        f"• Base Candles: {ltf_demand['Base_Count']}\n\n"
                        f"<b>III. POSITION SIZING (Risk Rs {RISK_PER_TRADE})</b>\n"
                        f"• Target: Rs {round(target, 2)}\n"
                        f"• Quantity: {qty} Shares"
                    )
                    send_telegram_alert(msg)

        # Supply Execution Logic: Favorable Curve + Favorable Trend
        if ltf_supply and curve_loc != "Low (Buy Preferred)" and itf_trend == "Bearish":
            pl, dl = ltf_supply['PL'], ltf_supply['DL']
            # Proximity check: Alert only if CMP is within 2% above the Proximal Line
            if pl * 0.98 <= cmp <= pl:
                risk = dl - pl
                if risk > 0:
                    qty = int(RISK_PER_TRADE / risk)
                    target = pl - (2 * risk) # 2:1 Reward to Risk Ratio
                    
                    msg = (
                        f"🔴 <b>GTF MTFA SUPPLY ALERT ({ltf_supply['Pattern']})</b>: {ticker}\n\n"
                        f"<b>I. MULTI-TIMEFRAME ALIGNMENT</b>\n"
                        f"• HTF Curve: {curve_loc}\n"
                        f"• ITF Trend: {itf_trend} (Below 20 EMA)\n\n"
                        f"<b>II. LTF EXECUTION ZONE</b>\n"
                        f"• CMP: Rs {round(cmp, 2)}\n"
                        f"• Entry (PL): Rs {pl}\n"
                        f"• Stop Loss (DL): Rs {dl}\n"
                        f"• Base Candles: {ltf_supply['Base_Count']}\n\n"
                        f"<b>III. POSITION SIZING (Risk Rs {RISK_PER_TRADE})</b>\n"
                        f"• Target: Rs {round(target, 2)}\n"
                        f"• Quantity: {qty} Shares"
                    )
                    send_telegram_alert(msg)

    except Exception as e:
        print(f"Computational Error evaluating {ticker}: {e}")

if __name__ == "__main__":
    for symbol in WATCHLIST:
        evaluate_mtfa(symbol)
