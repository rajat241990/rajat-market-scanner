import os
import requests
import numpy as np
import pandas as pd
import yfinance as yf

# ==============================================================================
# CONFIGURATION & GTF SOP v4.2 PARAMETERS
# ==============================================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_CAPITAL = 100000.0  # INR base capital
RISK_PERCENT = 1.0       # 1% Beginner, 1.5% Intermediate, 2% Pro
RISK_PER_TRADE = BASE_CAPITAL * (RISK_PERCENT / 100.0)

# Timeframe Triplet Architecture
ACTIVE_TRIPLET = "WIT"

TRIPLETS = {
    "HIT": {"htf": "60m", "itf": "15m", "ltf": "5m",  "p_htf": "1mo", "p_itf": "5d",  "p_ltf": "2d"},
    "DIT": {"htf": "1d",  "itf": "60m", "ltf": "15m", "p_htf": "2y",  "p_itf": "1mo", "p_ltf": "5d"},
    "WIT": {"htf": "1wk", "itf": "1d",  "ltf": "60m", "p_htf": "5y",  "p_itf": "1y",  "p_ltf": "1mo"},
    "MIT": {"htf": "1mo", "itf": "1wk", "ltf": "1d",  "p_htf": "10y", "p_itf": "3y",  "p_ltf": "1y"}
}

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

def send_telegram_alert(message: str):
    """Dispatches HTML-formatted institutional alert to Telegram."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"Telegram Notification Failure: {e}")

# ==============================================================================
# PHASE 1: DATA INGESTION & CANDLE CLASSIFICATION
# ==============================================================================
def get_historical_data(ticker: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(ticker, interval=interval, period=period, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    return df

def classify_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    GTF Candle Definitions:
    - Exciting: Body / Range > 0.50
    - Base: Body / Range <= 0.50
    """
    df = df.copy()
    df['Range'] = df['High'] - df['Low']
    df['Range'] = np.where(df['Range'] == 0, 1e-4, df['Range'])
    df['Body'] = np.abs(df['Close'] - df['Open'])
    df['Ratio'] = df['Body'] / df['Range']

    df['Is_Exciting'] = df['Ratio'] > 0.50
    df['Is_Base'] = df['Ratio'] <= 0.50
    df['Is_Green'] = df['Close'] > df['Open']
    df['Is_Red'] = df['Close'] < df['Open']

    # Invisible leg-out identification via gaps
    df['Gap_Up'] = df['Open'] > df['Close'].shift(1)
    df['Gap_Down'] = df['Open'] < df['Close'].shift(1)

    # Moving averages & trend proxies
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['SMA7'] = df['Close'].rolling(window=7).mean()
    return df

# ==============================================================================
# PHASE 4: ZONE DETECTION & EXCEPTIONAL MARKING ARCHITECTURE
# ==============================================================================
def find_all_zones(df: pd.DataFrame, zone_type: str = "Demand", max_base: int = 5) -> list:
    """
    Identifies zones in reverse chronological order (most recent first).
    Applies strict B2W Proximal Line and Exceptional Marking Distal Line rules.
    """
    zones = []
    n = len(df)
    if n < 8:
        return zones
        
    cmp = float(df['Close'].iloc[-1])

    # Scan backwards from the most recent closed candle
    for i in range(n - 2, 3, -1):
        leg_out = df.iloc[i + 1]

        # Validate leg-out candle
        is_leg_out_valid = leg_out['Is_Exciting'] or \
            (zone_type == "Demand" and leg_out['Gap_Up']) or \
            (zone_type == "Supply" and leg_out['Gap_Down'])
        
        if not is_leg_out_valid:
            continue
        if zone_type == "Demand" and not leg_out['Is_Green']:
            continue
        if zone_type == "Supply" and not leg_out['Is_Red']:
            continue

        # Extract base candles (1 to 5 allowed)
        base_candles = []
        base_indices = []
        for j in range(i, max(-1, i - max_base - 1), -1):
            if df['Is_Base'].iloc[j]:
                base_candles.append(df.iloc[j])
                base_indices.append(j)
            else:
                break

        base_count = len(base_candles)
        if base_count < 1 or base_count > max_base:
            continue

        # Validate leg-in candle
        leg_in_idx = base_indices[-1] - 1
        if leg_in_idx < 0:
            continue
        leg_in = df.iloc[leg_in_idx]
        if not leg_in['Is_Exciting']:
            continue

        base_df = pd.DataFrame(base_candles)
        
        # Determine Pattern & Mark Boundaries
        if zone_type == "Demand":
            pattern = "DBR" if leg_in['Is_Red'] else "RBR"
            
            # Closing Concept: Leg-out closes above leg-in body high
            leg_in_high = max(leg_in['Open'], leg_in['Close'])
            closing_concept = leg_out['Close'] > leg_in_high

            # PL: Highest body among base candles (Body-to-Wick Rule)
            pl = float(base_df[['Open', 'Close']].max().max())

            # DL: Exceptional Marking Rules
            base_min_wick = float(base_df['Low'].min())
            if pattern == "DBR":  # Reversal: Check leg-in, base, and leg-out
                dl = float(min(leg_in['Low'], base_min_wick, leg_out['Low']))
            else:                 # Continuous (RBR): Check base and leg-out wicks only
                dl = float(min(base_min_wick, leg_out['Low']))

            if pl >= cmp:  # Demand must sit strictly below CMP
                continue

        else:  # Supply Zone
            pattern = "RBD" if leg_in['Is_Green'] else "DBD"
            
            # Closing Concept: Leg-out closes below leg-in body low
            leg_in_low = min(leg_in['Open'], leg_in['Close'])
            closing_concept = leg_out['Close'] < leg_in_low

            # PL: Lowest body among base candles
            pl = float(base_df[['Open', 'Close']].min().min())

            # DL: Exceptional Marking Rules
            base_max_wick = float(base_df['High'].max())
            if pattern == "RBD":  # Reversal: Check leg-in, base, and leg-out
                dl = float(max(leg_in['High'], base_max_wick, leg_out['High']))
            else:                 # Continuous (DBD): Check base and leg-out wicks only
                dl = float(max(base_max_wick, leg_out['High']))

            if pl <= cmp:  # Supply must sit strictly above CMP
                continue

        # Audit Historical Price Path for Freshness & Breaches
        post_zone_df = df.iloc[i + 2:]
        is_fresh = True
        is_breached = False
        tested_count = 0

        if not post_zone_df.empty:
            for _, candle in post_zone_df.iterrows():
                if zone_type == "Demand":
                    if candle['Low'] < dl:
                        is_breached = True
                        break
                    elif candle['Low'] <= pl:
                        is_fresh = False
                        tested_count += 1
                else:
                    if candle['High'] > dl:
                        is_breached = True
                        break
                    elif candle['High'] >= pl:
                        is_fresh = False
                        tested_count += 1

        if is_breached:
            continue

        # GTF 7-Point SOP Scoring Matrix
        fresh_pts = 3.0 if is_fresh else (1.5 if tested_count == 1 else 0.0)
        has_double_exciting = (len(df) > i + 2 and df['Is_Exciting'].iloc[i + 2])
        strength_pts = 2.0 if (has_double_exciting or leg_out['Gap_Up'] or leg_out['Gap_Down']) else 1.0
        time_pts = 2.0 if base_count <= 3 else (1.0 if base_count <= 5 else 0.0)
        
        base_score = fresh_pts + strength_pts + time_pts

        zones.append({
            "Type": zone_type,
            "Pattern": pattern,
            "PL": round(pl, 2),
            "DL": round(dl, 2),
            "Date": str(df.index[base_indices[-1]])[:10],
            "Base_Count": base_count,
            "Is_Fresh": is_fresh,
            "Tested_Count": tested_count,
            "Closing_Concept": closing_concept,
            "Base_Score": base_score,
            "Index": i
        })

    return zones

# ==============================================================================
# PHASE 2: HTF CURVE TRISECTION (MOST RECENT FORMATION ENFORCEMENT)
# ==============================================================================
def evaluate_htf_curve(df_htf: pd.DataFrame, cmp: float):
    """
    Enforces the HTF Curve rule:
    Extracts strictly the MOST RECENT fresh demand and supply formations.
    Ignores all distant or older historical zones on HTF.
    """
    htf_demands = find_all_zones(df_htf, "Demand")
    htf_supplies = find_all_zones(df_htf, "Supply")

    # Strictly select the first element (most recent chronological formation)
    recent_htf_dem = htf_demands[0] if len(htf_demands) > 0 else None
    recent_htf_sup = htf_supplies[0] if len(htf_supplies) > 0 else None

    if not recent_htf_dem and not recent_htf_sup:
        return "Equilibrium (No Zones)", "Neutral", 0.0, 0.0, 0.0, None, None

    dem_pl = recent_htf_dem['PL'] if recent_htf_dem else cmp * 0.85
    sup_pl = recent_htf_sup['PL'] if recent_htf_sup else cmp * 1.15
    spread = sup_pl - dem_pl

    if spread <= 0:
        return "Equilibrium (Compressed)", "Follow Trend", dem_pl, sup_pl, 0.0, recent_htf_dem, recent_htf_sup

    # Divide spread into 3 equal trisections
    lower_third = dem_pl + (spread / 3.0)
    upper_third = sup_pl - (spread / 3.0)

    if cmp <= dem_pl:
        location = "Very Low on Curve (Inside Demand)"
        bias = "Definitely Buy"
    elif dem_pl < cmp <= lower_third:
        location = "Low on Curve"
        bias = "Buy"
    elif lower_third < cmp < upper_third:
        location = "Equilibrium (EQB)"
        bias = "Follow Trend"
    elif upper_third <= cmp < sup_pl:
        location = "High on Curve"
        bias = "Sell"
    else:
        location = "Very High on Curve (Inside Supply)"
        bias = "Definitely Sell"

    return location, bias, dem_pl, sup_pl, spread, recent_htf_dem, recent_htf_sup

# ==============================================================================
# PHASE 3: ITF TREND & MOMENTUM VALIDATION
# ==============================================================================
def evaluate_itf_trend(df_itf: pd.DataFrame) -> dict:
    cmp = float(df_itf['Close'].iloc[-1])
    ema20 = float(df_itf['EMA20'].iloc[-1])
    ema50 = float(df_itf['EMA50'].iloc[-1])
    sma7 = float(df_itf['SMA7'].iloc[-1])
    sma7_prev = float(df_itf['SMA7'].iloc[-3])

    golden_cross = ema20 > ema50
    above_ema20 = cmp > ema20
    sma7_rising = sma7 > sma7_prev

    # Structure Check: Higher Highs / Higher Lows vs Lower Highs / Lower Lows
    recent_highs = df_itf['High'].iloc[-10:].values
    recent_lows = df_itf['Low'].iloc[-10:].values
    is_hh_hl = recent_highs[-1] > np.median(recent_highs) and recent_lows[-1] > np.median(recent_lows)

    if above_ema20 and golden_cross:
        direction = "Bullish"
    elif not above_ema20 and not golden_cross:
        direction = "Bearish"
    else:
        direction = "Sideways / Transition"

    return {
        "Direction": direction,
        "EMA20": round(ema20, 2),
        "EMA50": round(ema50, 2),
        "Golden_Cross": golden_cross,
        "Above_EMA20": above_ema20,
        "SMA7_Direction": "Rising" if sma7_rising else "Falling",
        "Structure": "HH/HL" if is_hh_hl else "LH/LL"
    }

# ==============================================================================
# PHASE 5: EXECUTION, CONFLUENCE SCORING & SIZING
# ==============================================================================
def run_sop_analysis(ticker: str):
    cfg = TRIPLETS[ACTIVE_TRIPLET]
    
    df_htf = get_historical_data(ticker, cfg['htf'], cfg['p_htf'])
    df_itf = get_historical_data(ticker, cfg['itf'], cfg['p_itf'])
    df_ltf = get_historical_data(ticker, cfg['ltf'], cfg['p_ltf'])

    if df_htf.empty or df_itf.empty or df_ltf.empty:
        return

    df_htf = classify_candles(df_htf)
    df_itf = classify_candles(df_itf)
    df_ltf = classify_candles(df_ltf)

    cmp = float(df_ltf['Close'].iloc[-1])

    # 1. Curve Location strictly using the MOST RECENT HTF formation
    curve_loc, curve_bias, dem_pl, sup_pl, spread, htf_dem, htf_sup = evaluate_htf_curve(df_htf, cmp)

    # 2. Trend Alignment
    itf_trend = evaluate_itf_trend(df_itf)

    # 3. Execution Zone Candidates
    ltf_demands = find_all_zones(df_ltf, "Demand")
    ltf_supplies = find_all_zones(df_ltf, "Supply")

    trade_side = None
    target_zones = []

    # SOP Action Mapping
    if "Buy" in curve_bias or (curve_loc.startswith("Equilibrium") and itf_trend["Direction"] == "Bullish"):
        trade_side = "BUY"
        target_zones = ltf_demands
    elif "Sell" in curve_bias or (curve_loc.startswith("Equilibrium") and itf_trend["Direction"] == "Bearish"):
        trade_side = "SELL"
        target_zones = ltf_supplies
    else:
        return

    if not target_zones:
        return

    # Select execution zone within active proximity (≤ 3.5% from CMP)
    selected_zone = None
    for z in target_zones:
        if trade_side == "BUY" and (z['PL'] <= cmp <= z['PL'] * 1.035):
            selected_zone = z
            break
        elif trade_side == "SELL" and (z['PL'] * 0.965 <= cmp <= z['PL']):
            selected_zone = z
            break

    if not selected_zone:
        return

    # Quantitative Confluence Scoring (Max 9/9)
    confluence_score = selected_zone['Base_Score']
    ltf_ema20 = float(df_ltf['EMA20'].iloc[-1])
    ltf_ema50 = float(df_ltf['EMA50'].iloc[-1])

    # EMA 20 Dynamic Support/Resistance Alignment (+1 pt)
    ema_aligned = abs(selected_zone['PL'] - ltf_ema20) / selected_zone['PL'] <= 0.02
    if ema_aligned:
        confluence_score += 1.0

    # Golden/Death Cross Confluence (+1 pt)
    cross_aligned = (trade_side == "BUY" and ltf_ema20 > ltf_ema50) or (trade_side == "SELL" and ltf_ema20 < ltf_ema50)
    if cross_aligned:
        confluence_score += 1.0

    # Filter out weak zones (Score strictly >= 5.5)
    if confluence_score < 5.5:
        return

    # Entry Strategy Selection
    if selected_zone['Base_Score'] >= 7.0 and selected_zone['Is_Fresh']:
        entry_type = "Entry Type 1 (Set & Forget)"
    elif selected_zone['Base_Score'] >= 6.0:
        entry_type = "Entry Type 2 (Wait for Inside Open Confirmation)"
    else:
        entry_type = "Entry Type 3 (Wait for Zone Exit Confirmation)"

    # Mathematical Risk & Position Sizing
    pl = selected_zone['PL']
    dl = selected_zone['DL']
    zone_height = abs(pl - dl)
    cushion = round(zone_height * 0.05, 2)

    if trade_side == "BUY":
        entry_px = round(pl + cushion, 2)
        stop_px = round(dl - cushion, 2)
        risk_per_share = round(entry_px - stop_px, 2)
        target_2r = round(entry_px + (2 * risk_per_share), 2)
    else:
        entry_px = round(pl - cushion, 2)
        stop_px = round(dl + cushion, 2)
        risk_per_share = round(stop_px - entry_px, 2)
        target_2r = round(entry_px - (2 * risk_per_share), 2)

    if risk_per_share <= 0:
        return

    qty = int(RISK_PER_TRADE / risk_per_share)
    trade_capital = round(qty * entry_px, 2)

    # Format Standardized Execution Report
    side_label = "🟢 LONG SETUP" if trade_side == "BUY" else "🔴 SHORT SETUP"
    
    # Calculate statuses beforehand to avoid f-string quote clashing
    freshness_status = "100% Fresh (Untested)" if selected_zone['Is_Fresh'] else f"Tested {selected_zone['Tested_Count']}x"
    closing_status = "PASSED (Decisive)" if selected_zone['Closing_Concept'] else "Standard"

    alert_msg = (
        f"{side_label}: <b>{ticker}</b> (GTF SOP v4.2)\n"
        f"<b>Active Triplet</b>: {ACTIVE_TRIPLET} ({cfg['htf']} | {cfg['itf']} | {cfg['ltf']})\n\n"
        f"<b>SECTION I: HTF LOCATION & CURVE (HTF: {cfg['htf']})</b>\n"
        f"• Curve Location: <b>{curve_loc}</b>\n"
        f"• Curve Action Bias: <b>{curve_bias}</b>\n"
        f"• Most Recent Demand Formation: PL Rs {htf_dem['PL'] if htf_dem else 'None'} | DL Rs {htf_dem['DL'] if htf_dem else 'None'}\n"
        f"• Most Recent Supply Formation: PL Rs {htf_sup['PL'] if htf_sup else 'None'} | DL Rs {htf_sup['DL'] if htf_sup else 'None'}\n"
        f"• Curve Trisection Spread: Rs {round(spread, 2)}\n\n"
        f"<b>SECTION II: ITF TREND & MOMENTUM (ITF: {cfg['itf']})</b>\n"
        f"• Trend Structure: <b>{itf_trend['Direction']} ({itf_trend['Structure']})</b>\n"
        f"• Dynamic 20 EMA: Rs {itf_trend['EMA20']} (Above: {itf_trend['Above_EMA20']})\n"
        f"• 7 SMA Direction: {itf_trend['SMA7_Direction']}\n"
        f"• Golden Crossover Status: {itf_trend['Golden_Cross']}\n\n"
        f"<b>SECTION III: LTF EXECUTION ZONE ARCHITECTURE (LTF: {cfg['ltf']})</b>\n"
        f"• Formation Pattern: <b>{selected_zone['Pattern']} ({selected_zone['Type']})</b>\n"
        f"• Formation Date: {selected_zone['Date']}\n"
        f"• Proximal Line (PL): Rs {pl} (B2W Marked)\n"
        f"• Distal Line (DL): Rs {dl} (Exceptional Wick Checked)\n"
        f"• Base Candles Count: {selected_zone['Base_Count']}\n"
        f"• Freshness Status: {freshness_status}\n"
        f"• Closing Concept: {closing_status}\n\n"
        f"<b>SECTION IV: QUANTITATIVE SCORING & EXECUTION</b>\n"
        f"• GTF Base Quality Score: <b>{selected_zone['Base_Score']}/7.0</b>\n"
        f"• Confluence Points: EMA20 (+{1.0 if ema_aligned else 0}) | Cross (+{1.0 if cross_aligned else 0})\n"
        f"• Final Institutional Score: <b>{confluence_score}/9.0</b>\n"
        f"• Strategy Execution Type: <b>{entry_type}</b>\n\n"
        f"<b>SECTION V: RISK MATRIX & SIZING (Capital Rs {BASE_CAPITAL})</b>\n"
        f"• Current Market Price (CMP): Rs {round(cmp, 2)}\n"
        f"• Planned Entry Order: Rs {entry_px}\n"
        f"• Structural Stop Loss: Rs {stop_px}\n"
        f"• Target Objective (2:1 RR): Rs {target_2r}\n"
        f"• Total Risk Allocation (1.0%): Rs {RISK_PER_TRADE}\n"
        f"• Execution Quantity: <b>{qty} Shares</b> (Outlay Rs {trade_capital})"
    )
    send_telegram_alert(alert_msg)

if __name__ == "__main__":
    for ticker_symbol in WATCHLIST:
        try:
            run_sop_analysis(ticker_symbol)
        except Exception as ex:
            print(f"[!] Processing exception on {ticker_symbol}: {ex}")
