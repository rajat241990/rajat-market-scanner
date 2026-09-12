import os
import sys
import logging
import subprocess

# ==============================================================================
# AUTO-INSTALL DEPENDENCIES
# ==============================================================================
def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        logging.info(f"Package '{package}' not found. Installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Ensure required third-party packages are installed before running
required_packages = ['requests', 'numpy', 'pandas', 'yfinance', 'mplfinance', 'scipy', 'matplotlib']
for pkg in required_packages:
    install_and_import(pkg)

# Now it is safe to import them
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt
from scipy.signal import argrelextrema

# ==============================================================================
# CONFIGURATION & GTF SOP v4.2 PARAMETERS
# ==============================================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_CAPITAL = 100000.0  # INR base capital
RISK_PERCENT = 1.0       # 1% Beginner, 1.5% Intermediate, 2% Pro
RISK_PER_TRADE = BASE_CAPITAL * (RISK_PERCENT / 100.0)
SWING_WINDOW = 15        # Lookback/forward window to confirm a swing point

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Timeframe Triplet Architecture
# Default to Monthly HTF (MIT) if the user does not specify one in the environment
ACTIVE_TRIPLET = os.getenv("ACTIVE_TRIPLET", "MIT")

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

def send_telegram_alert(message: str, chart_path: str = None):
    """Dispatches HTML-formatted institutional alert and optional chart to Telegram."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logging.info("Telegram not configured. Printing locally:\n\n" + message)
        return
        
    # Send Image if available
    if chart_path and os.path.exists(chart_path):
        url_photo = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        try:
            with open(chart_path, 'rb') as photo:
                requests.post(url_photo, data={'chat_id': CHAT_ID}, files={'photo': photo}, timeout=15)
        except Exception as e:
            logging.error(f"Telegram Photo Send Failure: {e}")

    # Send HTML Text Execution Details
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        res = requests.post(url_msg, json=payload, timeout=10)
        res.raise_for_status()
    except Exception as e:
        logging.error(f"Telegram Text Notification Failure: {e}")

# ==============================================================================
# PHASE 1: DATA INGESTION & CLASSIFICATION
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
    df = df.copy()
    df['Range'] = df['High'] - df['Low']
    df['Range'] = np.where(df['Range'] == 0, 1e-4, df['Range'])
    df['Body'] = np.abs(df['Close'] - df['Open'])
    df['Ratio'] = df['Body'] / df['Range']

    df['Is_Exciting'] = df['Ratio'] > 0.50
    df['Is_Base'] = df['Ratio'] <= 0.50
    df['Is_Green'] = df['Close'] > df['Open']
    df['Is_Red'] = df['Close'] < df['Open']

    df['Gap_Up'] = df['Open'] > df['Close'].shift(1)
    df['Gap_Down'] = df['Open'] < df['Close'].shift(1)

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['SMA7'] = df['Close'].rolling(window=7).mean()
    return df

# ==============================================================================
# PHASE 2: ZONE DETECTION
# ==============================================================================
def find_all_zones(df: pd.DataFrame, zone_type: str = "Demand", max_base: int = 5) -> list:
    zones = []
    n = len(df)
    if n < 8: return zones
        
    cmp = float(df['Close'].iloc[-1])

    for i in range(n - 2, 3, -1):
        leg_out = df.iloc[i + 1]

        is_leg_out_valid = leg_out['Is_Exciting'] or \
            (zone_type == "Demand" and leg_out['Gap_Up']) or \
            (zone_type == "Supply" and leg_out['Gap_Down'])
        
        if not is_leg_out_valid: continue
        if zone_type == "Demand" and not leg_out['Is_Green']: continue
        if zone_type == "Supply" and not leg_out['Is_Red']: continue

        base_candles, base_indices = [], []
        for j in range(i, max(-1, i - max_base - 1), -1):
            if df['Is_Base'].iloc[j]:
                base_candles.append(df.iloc[j])
                base_indices.append(j)
            else:
                break

        base_count = len(base_candles)
        if base_count < 1 or base_count > max_base: continue

        leg_in_idx = base_indices[-1] - 1
        if leg_in_idx < 0: continue
        leg_in = df.iloc[leg_in_idx]
        if not leg_in['Is_Exciting']: continue

        base_df = pd.DataFrame(base_candles)
        
        if zone_type == "Demand":
            pattern = "DBR" if leg_in['Is_Red'] else "RBR"
            leg_in_high = max(leg_in['Open'], leg_in['Close'])
            closing_concept = leg_out['Close'] > leg_in_high
            pl = float(base_df[['Open', 'Close']].max().max())
            base_min_wick = float(base_df['Low'].min())
            
            if pattern == "DBR": dl = float(min(leg_in['Low'], base_min_wick, leg_out['Low']))
            else: dl = float(min(base_min_wick, leg_out['Low']))
            if pl >= cmp: continue

        else:
            pattern = "RBD" if leg_in['Is_Green'] else "DBD"
            leg_in_low = min(leg_in['Open'], leg_in['Close'])
            closing_concept = leg_out['Close'] < leg_in_low
            pl = float(base_df[['Open', 'Close']].min().min())
            base_max_wick = float(base_df['High'].max())
            
            if pattern == "RBD": dl = float(max(leg_in['High'], base_max_wick, leg_out['High']))
            else: dl = float(max(base_max_wick, leg_out['High']))
            if pl <= cmp: continue

        post_zone_df = df.iloc[i + 2:]
        is_fresh, is_breached, tested_count = True, False, 0

        if not post_zone_df.empty:
            for _, candle in post_zone_df.iterrows():
                if zone_type == "Demand":
                    if candle['Low'] < dl: is_breached = True; break
                    elif candle['Low'] <= pl: is_fresh = False; tested_count += 1
                else:
                    if candle['High'] > dl: is_breached = True; break
                    elif candle['High'] >= pl: is_fresh = False; tested_count += 1

        if is_breached: continue

        fresh_pts = 3.0 if is_fresh else (1.5 if tested_count == 1 else 0.0)
        has_double_exciting = (len(df) > i + 2 and df['Is_Exciting'].iloc[i + 2])
        strength_pts = 2.0 if (has_double_exciting or leg_out['Gap_Up'] or leg_out['Gap_Down']) else 1.0
        time_pts = 2.0 if base_count <= 3 else (1.0 if base_count <= 5 else 0.0)
        
        zones.append({
            "Type": zone_type, "Pattern": pattern,
            "PL": round(pl, 2), "DL": round(dl, 2),
            "Date": str(df.index[base_indices[-1]])[:10],
            "Base_Count": base_count, "Is_Fresh": is_fresh,
            "Tested_Count": tested_count, "Closing_Concept": closing_concept,
            "Base_Score": fresh_pts + strength_pts + time_pts, "Index": i
        })

    return zones

def evaluate_htf_curve(df_htf: pd.DataFrame, cmp: float):
    htf_demands = find_all_zones(df_htf, "Demand")
    htf_supplies = find_all_zones(df_htf, "Supply")

    recent_htf_dem = htf_demands[0] if len(htf_demands) > 0 else None
    recent_htf_sup = htf_supplies[0] if len(htf_supplies) > 0 else None

    if not recent_htf_dem and not recent_htf_sup:
        return "Equilibrium (No Zones)", "Neutral", 0.0, 0.0, 0.0, None, None

    dem_pl = recent_htf_dem['PL'] if recent_htf_dem else cmp * 0.85
    sup_pl = recent_htf_sup['PL'] if recent_htf_sup else cmp * 1.15
    spread = sup_pl - dem_pl

    if spread <= 0: return "Equilibrium (Compressed)", "Follow Trend", dem_pl, sup_pl, 0.0, recent_htf_dem, recent_htf_sup

    lower_third = dem_pl + (spread / 3.0)
    upper_third = sup_pl - (spread / 3.0)

    if cmp <= dem_pl: location, bias = "Very Low on Curve (Inside Demand)", "Definitely Buy"
    elif dem_pl < cmp <= lower_third: location, bias = "Low on Curve", "Buy"
    elif lower_third < cmp < upper_third: location, bias = "Equilibrium (EQB)", "Follow Trend"
    elif upper_third <= cmp < sup_pl: location, bias = "High on Curve", "Sell"
    else: location, bias = "Very High on Curve (Inside Supply)", "Definitely Sell"

    return location, bias, dem_pl, sup_pl, spread, recent_htf_dem, recent_htf_sup

def evaluate_itf_trend(df_itf: pd.DataFrame) -> dict:
    cmp = float(df_itf['Close'].iloc[-1])
    ema20, ema50 = float(df_itf['EMA20'].iloc[-1]), float(df_itf['EMA50'].iloc[-1])
    sma7 = float(df_itf['SMA7'].iloc[-1])
    sma7_prev = float(df_itf['SMA7'].iloc[-3])

    golden_cross = ema20 > ema50
    above_ema20 = cmp > ema20
    sma7_rising = sma7 > sma7_prev

    recent_highs = df_itf['High'].iloc[-10:].values
    recent_lows = df_itf['Low'].iloc[-10:].values
    is_hh_hl = recent_highs[-1] > np.median(recent_highs) and recent_lows[-1] > np.median(recent_lows)

    if above_ema20 and golden_cross: direction = "Bullish"
    elif not above_ema20 and not golden_cross: direction = "Bearish"
    else: direction = "Sideways / Transition"

    return {
        "Direction": direction, "EMA20": round(ema20, 2), "EMA50": round(ema50, 2),
        "Golden_Cross": golden_cross, "Above_EMA20": above_ema20,
        "SMA7_Direction": "Rising" if sma7_rising else "Falling",
        "Structure": "HH/HL" if is_hh_hl else "LH/LL"
    }

# ==============================================================================
# PHASE 3: SWING, FIBONACCI & CHART GENERATION
# ==============================================================================
def get_swings_and_fibs(df: pd.DataFrame, window=SWING_WINDOW):
    """Calculates Swings and Fibonacci levels using scipy."""
    highs = df['High'].values
    lows = df['Low'].values

    local_max_idx = argrelextrema(highs, np.greater, order=window)[0]
    local_min_idx = argrelextrema(lows, np.less, order=window)[0]

    if len(local_max_idx) == 0 or len(local_min_idx) == 0:
        return None, None, None, {}

    last_high_idx = local_max_idx[-1]
    last_low_idx = local_min_idx[-1]

    swing_high = {'date': df.index[last_high_idx], 'price': highs[last_high_idx]}
    swing_low = {'date': df.index[last_low_idx], 'price': lows[last_low_idx]}

    trend = "Upward" if last_low_idx < last_high_idx else "Downward"

    H = swing_high['price']
    L = swing_low['price']
    diff = H - L
    
    ratios = [0.0, 0.236, 0.382, 0.500, 0.618, 0.786, 1.0]
    fib_levels = {}
    for ratio in ratios:
        if trend == "Upward": fib_levels[f"{ratio:.3f}"] = H - (ratio * diff)
        else: fib_levels[f"{ratio:.3f}"] = L + (ratio * diff)

    return swing_high, swing_low, trend, fib_levels

def generate_chart(ticker: str, df: pd.DataFrame, swing_high: dict, swing_low: dict, fib_levels: dict, score: float):
    """Generates mplfinance candlestick chart with EMAs, Swings, and Fib levels."""
    plot_df = df.tail(120).copy()
    if plot_df.empty: return None
    
    chart_file = f"chart_{ticker}.png"
    add_plots = [
        mpf.make_addplot(plot_df['EMA20'], color='blue', width=1.5, label='EMA 20'),
        mpf.make_addplot(plot_df['EMA50'], color='orange', width=1.5, label='EMA 50')
    ]

    hlines_data = []
    if "0.500" in fib_levels and "0.618" in fib_levels:
        hlines_data = [fib_levels["0.500"], fib_levels["0.618"]]

    hlines = dict(hlines=hlines_data, colors=['g', 'r'], linestyle='--', linewidths=1.5, alpha=0.7) if hlines_data else None

    fig, axlist = mpf.plot(
        plot_df, type='candle', style='yahoo', addplot=add_plots, hlines=hlines,
        title=f"\n{ticker} - Score: {score}/9.0", ylabel='Price', volume=False, 
        figsize=(10, 6), returnfig=True
    )

    ax = axlist[0]
    start_date = plot_df.index[0]
    
    if swing_high and swing_high['date'] >= start_date:
        ax.annotate('Swing High', xy=(swing_high['date'], swing_high['price']),
                    xytext=(10, 10), textcoords='offset points', arrowprops=dict(arrowstyle="->", color='red'))
                    
    if swing_low and swing_low['date'] >= start_date:
        ax.annotate('Swing Low', xy=(swing_low['date'], swing_low['price']),
                    xytext=(10, -20), textcoords='offset points', arrowprops=dict(arrowstyle="->", color='green'))

    fig.savefig(chart_file, bbox_inches='tight')
    plt.close(fig) # Prevent memory leaks
    return chart_file

# ==============================================================================
# PHASE 4: EXECUTION & SCORING
# ==============================================================================
def run_sop_analysis(ticker: str):
    cfg = TRIPLETS[ACTIVE_TRIPLET]
    
    df_htf = get_historical_data(ticker, cfg['htf'], cfg['p_htf'])
    df_itf = get_historical_data(ticker, cfg['itf'], cfg['p_itf'])
    df_ltf = get_historical_data(ticker, cfg['ltf'], cfg['p_ltf'])

    if df_htf.empty or df_itf.empty or df_ltf.empty: return

    df_htf = classify_candles(df_htf)
    df_itf = classify_candles(df_itf)
    df_ltf = classify_candles(df_ltf)

    cmp = float(df_ltf['Close'].iloc[-1])

    curve_loc, curve_bias, dem_pl, sup_pl, spread, htf_dem, htf_sup = evaluate_htf_curve(df_htf, cmp)
    itf_trend = evaluate_itf_trend(df_itf)

    ltf_demands = find_all_zones(df_ltf, "Demand")
    ltf_supplies = find_all_zones(df_ltf, "Supply")

    trade_side, target_zones = None, []
    if "Buy" in curve_bias or (curve_loc.startswith("Equilibrium") and itf_trend["Direction"] == "Bullish"):
        trade_side, target_zones = "BUY", ltf_demands
    elif "Sell" in curve_bias or (curve_loc.startswith("Equilibrium") and itf_trend["Direction"] == "Bearish"):
        trade_side, target_zones = "SELL", ltf_supplies
    else: return

    if not target_zones: return

    selected_zone = None
    for z in target_zones:
        if trade_side == "BUY" and (z['PL'] <= cmp <= z['PL'] * 1.035):
            selected_zone = z; break
        elif trade_side == "SELL" and (z['PL'] * 0.965 <= cmp <= z['PL']):
            selected_zone = z; break

    if not selected_zone: return

    confluence_score = selected_zone['Base_Score']
    ltf_ema20, ltf_ema50 = float(df_ltf['EMA20'].iloc[-1]), float(df_ltf['EMA50'].iloc[-1])

    ema_aligned = abs(selected_zone['PL'] - ltf_ema20) / selected_zone['PL'] <= 0.02
    if ema_aligned: confluence_score += 1.0

    cross_aligned = (trade_side == "BUY" and ltf_ema20 > ltf_ema50) or (trade_side == "SELL" and ltf_ema20 < ltf_ema50)
    if cross_aligned: confluence_score += 1.0

    # Strict Score Filter (DO NOT DISPATCH < 5.5)
    if confluence_score < 5.5: return

    # Gather Swing & Fib details for the alert (Calculating on ITF)
    swing_high, swing_low, trend, fib_levels = get_swings_and_fibs(df_itf, SWING_WINDOW)

    entry_type = "Entry Type 1 (Set & Forget)" if selected_zone['Base_Score'] >= 7.0 and selected_zone['Is_Fresh'] else \
                 "Entry Type 2 (Wait Inside Confirm)" if selected_zone['Base_Score'] >= 6.0 else "Entry Type 3 (Wait Exit Confirm)"

    pl, dl = selected_zone['PL'], selected_zone['DL']
    zone_height = abs(pl - dl)
    cushion = round(zone_height * 0.05, 2)

    if trade_side == "BUY":
        entry_px, stop_px = round(pl + cushion, 2), round(dl - cushion, 2)
        risk_per_share = round(entry_px - stop_px, 2)
        target_2r = round(entry_px + (2 * risk_per_share), 2)
    else:
        entry_px, stop_px = round(pl - cushion, 2), round(dl + cushion, 2)
        risk_per_share = round(stop_px - entry_px, 2)
        target_2r = round(entry_px - (2 * risk_per_share), 2)

    if risk_per_share <= 0: return
    qty = int(RISK_PER_TRADE / risk_per_share)
    trade_capital = round(qty * entry_px, 2)

    side_label = "🟢 LONG SETUP" if trade_side == "BUY" else "🔴 SHORT SETUP"
    freshness_status = "100% Fresh (Untested)" if selected_zone['Is_Fresh'] else f"Tested {selected_zone['Tested_Count']}x"
    closing_status = "PASSED (Decisive)" if selected_zone['Closing_Concept'] else "Standard"

    # Fibonacci Formatting logic
    fib_500 = fib_levels.get('0.500') if fib_levels else None
    fib_618 = fib_levels.get('0.618') if fib_levels else None
    fib_500_str = f"Rs {fib_500:.2f}" if fib_500 else "N/A"
    fib_618_str = f"Rs {fib_618:.2f}" if fib_618 else "N/A"
    swing_h_str = f"Rs {swing_high['price']:.2f}" if swing_high else "N/A"
    swing_l_str = f"Rs {swing_low['price']:.2f}" if swing_low else "N/A"

    if fib_500 and fib_618:
        zone_high, zone_low = max(fib_500, fib_618), min(fib_500, fib_618)
        is_golden = zone_low <= pl <= zone_high
        golden_status = "✅ PL is inside Golden Zone" if is_golden else "❌ PL is outside Golden Zone"
    else:
        golden_status = "N/A (Swings not found)"

    # Formatted Message Output
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

        f"<b>SECTION IV: SWING & FIBONACCI (ITF: {cfg['itf']})</b>\n"
        f"• Swing Trend Bias: <b>{trend if trend else 'N/A'}</b>\n"
        f"• Swing High: {swing_h_str} | Swing Low: {swing_l_str}\n"
        f"• Fib 0.500: {fib_500_str} | Fib 0.618: {fib_618_str}\n"
        f"• Golden Zone Status: <b>{golden_status}</b>\n\n"
        
        f"<b>SECTION V: QUANTITATIVE SCORING & EXECUTION</b>\n"
        f"• GTF Base Quality Score: <b>{selected_zone['Base_Score']}/7.0</b>\n"
        f"• Confluence Points: EMA20 (+{1.0 if ema_aligned else 0}) | Cross (+{1.0 if cross_aligned else 0})\n"
        f"• Final Institutional Score: <b>{confluence_score}/9.0</b>\n"
        f"• Strategy Execution Type: <b>{entry_type}</b>\n\n"
        
        f"<b>SECTION VI: RISK MATRIX & SIZING (Capital Rs {BASE_CAPITAL})</b>\n"
        f"• Current Market Price (CMP): Rs {round(cmp, 2)}\n"
        f"• Planned Entry Order: Rs {entry_px}\n"
        f"• Structural Stop Loss: Rs {stop_px}\n"
        f"• Target Objective (2:1 RR): Rs {target_2r}\n"
        f"• Total Risk Allocation (1.0%): Rs {RISK_PER_TRADE}\n"
        f"• Execution Quantity: <b>{qty} Shares</b> (Outlay Rs {trade_capital})"
    )

    # Generate Chart and dispatch
    chart_path = generate_chart(ticker, df_itf, swing_high, swing_low, fib_levels, confluence_score)
    send_telegram_alert(alert_msg, chart_path)

    # Cleanup Local Image File
    if chart_path and os.path.exists(chart_path):
        os.remove(chart_path)

if __name__ == "__main__":
    for ticker_symbol in WATCHLIST:
        try:
            logging.info(f"Scanning {ticker_symbol}...")
            run_sop_analysis(ticker_symbol)
        except Exception as ex:
            logging.error(f"Processing exception on {ticker_symbol}: {ex}")
