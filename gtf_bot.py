import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

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
    """Dispatches HTML-formatted alerts to Telegram."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(message)  # Fallback to console if credentials missing
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def classify_candles(df):
    """
    Vectorized classification of Exciting vs. Base candles using Numpy.
    Much faster than row-by-row iteration for yfinance dataframes.
    """
    df = df.copy()
    df['Range'] = df['High'] - df['Low']
    df['Body'] = abs(df['Close'] - df['Open'])
    
    # Handle zero range to avoid division by zero errors in illiquid assets
    df['Range'] = np.where(df['Range'] == 0, 0.0001, df['Range'])
    
    df['Ratio'] = df['Body'] / df['Range']
    df['Is_Exciting'] = df['Ratio'] > 0.50
    df['Is_Base'] = df['Ratio'] <= 0.50
    df['Color'] = np.where(df['Close'] > df['Open'], 'Green', 'Red')
    return df

def detect_zones(df, zone_type="Demand", cmp=None):
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
        if not leg_out['Is_Exciting']: continue
        if zone_type == "Demand" and leg_out['Color'] != 'Green': continue
        if zone_type == "Supply" and leg_out['Color'] != 'Red': continue

        # Condition 2: Trace back to find 1 to 6 Base candles
        base_candles = []
        base_idx = []
        for j in range(i, max(0, i - 6), -1):
            if df.iloc[j]['Is_Base']:
                base_candles.append(df.iloc[j])
                base_idx.append(j)
            else:
                break
                
        if len(base_candles) == 0 or len(base_candles) > 6:
            continue
            
        # Condition 3: Check for the Leg-In preceding the bases
        leg_in_idx = base_idx[-1] - 1
        leg_in = df.iloc[leg_in_idx]
        if not leg_in['Is_Exciting']:
            continue

        # Condition 4: Closing Concept (Achievement of liquidity consumption)
        if zone_type == "Demand" and leg_out['Close'] <= leg_in['High']:
            continue # Failed to absorb resting sellers
        if zone_type == "Supply" and leg_out['Close'] >= leg_in['Low']:
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
            pl = base_df[['Open', 'Close']].max().max()
            if cmp is not None and pl > cmp: continue # HTF Demand must be below CMP
        else:
            pl = base_df[['Open', 'Close']].min().min()
            if cmp is not None and pl < cmp: continue # HTF Supply must be above CMP

        # Calculate Distal Line (DL) with Exceptional Marking Logic
        dl = 0.0
        if zone_type == "Demand":
            base_lowest_wick = base_df['Low'].min()
            out_lowest_wick = leg_out['Low']
            in_lowest_wick = leg_in['Low']
            
            if pattern == "DBR": # Reversal
                dl = min(in_lowest_wick, base_lowest_wick, out_lowest_wick)
            else: # RBR (Ignore leg-in for continuous patterns)
                dl = min(base_lowest_wick, out_lowest_wick)
                
        elif zone_type == "Supply":
            base_highest_wick = base_df['High'].max()
            out_highest_wick = leg_out['High']
            in_highest_wick = leg_in['High']
            
            if pattern == "RBD": # Reversal
                dl = max(in_highest_wick, base_highest_wick, out_highest_wick)
            else: # DBD (Ignore leg-in for continuous patterns)
                dl = max(base_highest_wick, out_highest_wick)

        # Freshness Check: Has price breached the PL since creation?
        post_zone_df = df.iloc[i+2:]
        if not post_zone_df.empty:
            if zone_type == "Demand" and (post_zone_df['Low'] <= pl).any():
                continue # Zone tested or broken; discard
            if zone_type == "Supply" and (post_zone_df['High'] >= pl).any():
                continue # Zone tested or broken; discard

        # Zone is authentic, structurally sound, and fresh.
        zones.append({
            'Pattern': pattern,
            'PL': round(pl, 2),
            'DL': round(dl, 2),
            'Base_Count': len(base_candles),
            'Index': i
        })
        
        # Break after finding the first most recent valid unbreached zone
        break 

    return zones[0] if zones else None

def evaluate_mtfa(ticker):
    """
    Fetches Monthly (HTF), Weekly (ITF), and Daily (LTF) data via yfinance.
    Evaluates Curve location, moving average Trend, and LTF Execution zones.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # 1. HTF Curve Analysis (Monthly)
        df_htf = stock.history(period="5y", interval="1mo")
        if df_htf.empty or len(df_htf) < 5: return
        df_htf = classify_candles(df
