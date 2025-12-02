#!/opt/homebrew/opt/python@3.12/bin/python3.12
"""
Enhanced VCP Pattern Detector with OBV Moving Average Integration
Based on Mark Minervini's Trend Template + OBV 21-day MA Analysis
 
Enhanced Selection Criteria (40-Point System):
1. Trend Template Met (Mark Minervini's 10 criteria) - 10 points
2. Market Cap > $100 million
3. Uptrend Nearing Breakout - 7 points
4. Higher Lows Pattern - 3 points
5. Volume Contracting - 6 points
6. OBV Analysis - 14 points (OBV 21-day MA: 3pts + Accumulation: 3pts + Price Higher Lows: 3pts + OBV Higher High: 1pt + Price Divergence: 4pts)

PLUS:
- Extension / Late Breakout Filter (no score, hard filter):
  * > +20% in last 10 days
  * > +8% above 20-day MA
  * Climactic wide-range bar on big volume in last 3 bars
  * Breakout age > 1 day over 40-day pivot
"""

import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timedelta
import time
import json
import os
import signal
import sys
from stock_symbols_1243 import STOCK_SYMBOLS, ETF_SYMBOLS
import warnings
warnings.filterwarnings('ignore')

# Global variable to handle graceful shutdown
scan_interrupted = False

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global scan_interrupted
    scan_interrupted = True
    print(f"\n⚠️  扫描中断信号接收! 正在安全停止...")
    print("   - 当前股票分析完成后将停止")
    print("   - 已处理的结果将被保存")
    print("   - 按 Ctrl+C 再次强制退出")

# Set up signal handler for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)

# ============ Enhanced VCP Selection Criteria with OBV ============
ENHANCED_VCP_OBV_CONFIG = {
    "data_period": "400d",  # Need more than 252 days for 52-week calculations
    "market_cap_min": 100_000_000,  # $100 million minimum market cap
    "trend_template_criteria": {
        "price_above_ma50": True,
        "price_above_ma150": True,
        "price_above_ma200": True,
        "ma50_above_ma150": True,
        "ma50_above_ma200": True,
        "ma150_above_ma200": True,
        "ma200_rising": True,
        "price_within_25pct_high": True,
        "price_above_30week_low": True,
        "relative_strength": True
    },
    "breakout_criteria": {
        "near_100day_high": 10,  # Within 10 candles of 100-day high
        "within_7pct_daily_high": 7.0,  # Within 7% of daily 100-day high
        "within_20pct_weekly_high": 20.0,  # Within 20% of weekly 100-day high
        "below_daily_high": True  # Must be below the high (not broken out yet)
    },
    "higher_lows_periods": [10, 20, 30],  # Check higher lows over these periods
    "volume_contraction_periods": [5, 10, 15, 20, 25, 30],  # Volume contraction lookback periods
    "obv_analysis": {
        "obv_ma_period": 21,  # OBV 21-day moving average
        "obv_trend_period": 10,  # Check OBV trend over 10 days
        "accumulation_threshold": 0.05  # 5% OBV accumulation threshold
    }
}

# Create results folder
RESULTS_BASE_DIR = "results"
DATE_FOLDER = datetime.now().strftime('%Y%m%d')
RESULTS_DIR = os.path.join(RESULTS_BASE_DIR, DATE_FOLDER)
os.makedirs(RESULTS_DIR, exist_ok=True)

def get_enhanced_stock_data_basic(symbol, period="400d"):
    """Get basic stock data for enhanced VCP analysis (without OBV for speed)"""
    try:
        # Get daily data
        daily_data = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=False)
        
        # Get weekly data
        weekly_data = yf.download(symbol, period=period, interval="1wk", progress=False, auto_adjust=False)
        
        if daily_data is None or len(daily_data) < 300:
            return None, None
        
        # Handle multi-level columns
        if isinstance(daily_data.columns, pd.MultiIndex):
            daily_data.columns = daily_data.columns.get_level_values(0)
        if isinstance(weekly_data.columns, pd.MultiIndex):
            weekly_data.columns = weekly_data.columns.get_level_values(0)
        
        # Calculate technical indicators for daily data
        daily_data['MA20'] = daily_data['Close'].rolling(window=20).mean()
        daily_data['MA50'] = daily_data['Close'].rolling(window=50).mean()
        daily_data['MA150'] = daily_data['Close'].rolling(window=150).mean()
        daily_data['MA200'] = daily_data['Close'].rolling(window=200).mean()
        
        # Volume indicators
        daily_data['Volume_MA20'] = daily_data['Volume'].rolling(window=20).mean()
        
        # ATR (Average True Range) calculation for volatility-adjusted breakout detection
        daily_data['TR'] = np.maximum(
            daily_data['High'] - daily_data['Low'],
            np.maximum(
                abs(daily_data['High'] - daily_data['Close'].shift(1)),
                abs(daily_data['Low'] - daily_data['Close'].shift(1))
            )
        )
        daily_data['ATR14'] = daily_data['TR'].rolling(window=14).mean()
        
        # Range calculations
        daily_data['High_100'] = daily_data['High'].rolling(window=100).max()
        daily_data['Close_High_50'] = daily_data['Close'].rolling(window=50).max()  # 50-day high of close prices
        daily_data['Low_100'] = daily_data['Low'].rolling(window=100).min()
        daily_data['Low_10'] = daily_data['Low'].rolling(window=10).min()
        daily_data['Low_20'] = daily_data['Low'].rolling(window=20).min()
        daily_data['Low_30'] = daily_data['Low'].rolling(window=30).min()
        
        # Weekly indicators
        if len(weekly_data) > 0:
            weekly_data['High_100'] = weekly_data['High'].rolling(window=100).max()
        
        return daily_data.dropna(), weekly_data.dropna()
        
    except Exception as e:
        print(f"获取 {symbol} 数据失败: {e}")
        return None, None

def add_obv_calculations(daily_data):
    """Add OBV calculations to existing data (called only when needed)"""
    try:
        # OBV Calculations
        daily_data['OBV'] = ta.volume.on_balance_volume(daily_data['Close'], daily_data['Volume'])
        daily_data['OBV_MA21'] = daily_data['OBV'].rolling(window=21).mean()
        daily_data['OBV_MA10'] = daily_data['OBV'].rolling(window=10).mean()
        return daily_data
    except Exception as e:
        print(f"OBV计算失败: {e}")
        return daily_data

def get_enhanced_stock_data_with_obv(symbol, period="400d"):
    """Get comprehensive stock data for enhanced VCP analysis with OBV (legacy function)"""
    daily_data, weekly_data = get_enhanced_stock_data_basic(symbol, period)
    if daily_data is not None:
        daily_data = add_obv_calculations(daily_data)
    return daily_data, weekly_data

def get_market_cap(symbol):
    """Get market capitalization for the stock"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        market_cap = info.get('marketCap', 0)
        return market_cap
    except:
        return 0

def check_obv_trend_analysis(daily_data):
    """Check OBV 21-day MA trend, accumulation signals, price higher lows, and OBV divergence"""
    if len(daily_data) < 50:
        return False, 0, {}
    
    details = {}
    score = 0
    
    # Get OBV and moving averages
    obv = daily_data['OBV']
    obv_ma21 = daily_data['OBV_MA21']
    obv_ma10 = daily_data['OBV_MA10']
    
    # 1. OBV 21-day MA Trending Up (3 points)
    obv_ma21_current = obv_ma21.iloc[-1]
    obv_ma21_10days_ago = obv_ma21.iloc[-10] if len(obv_ma21) >= 10 else obv_ma21_current
    
    obv_ma21_trending_up = obv_ma21_current > obv_ma21_10days_ago
    details['obv_ma21_trending_up'] = obv_ma21_trending_up
    details['obv_ma21_current'] = round(obv_ma21_current, 0)
    details['obv_ma21_10days_ago'] = round(obv_ma21_10days_ago, 0)
    details['obv_ma21_change_pct'] = round((obv_ma21_current - obv_ma21_10days_ago) / abs(obv_ma21_10days_ago) * 100, 2) if obv_ma21_10days_ago != 0 else 0
    
    if obv_ma21_trending_up:
        score += 3
    
    # 2. OBV Accumulation Signal (3 points)
    obv_current = obv.iloc[-1]
    obv_21days_ago = obv.iloc[-21] if len(obv) >= 21 else obv_current
    price_current = daily_data['Close'].iloc[-1]
    price_21days_ago = daily_data['Close'].iloc[-21] if len(daily_data) >= 21 else price_current
    
    obv_change_pct = (obv_current - obv_21days_ago) / abs(obv_21days_ago) * 100 if obv_21days_ago != 0 else 0
    price_change_pct = (price_current - price_21days_ago) / price_21days_ago * 100 if price_21days_ago != 0 else 0
    
    accumulation_signal = obv_change_pct > 0 and (obv_change_pct > price_change_pct or abs(price_change_pct) < 5)
    
    details['accumulation_signal'] = accumulation_signal
    details['obv_change_21d_pct'] = round(obv_change_pct, 2)
    details['price_change_21d_pct'] = round(price_change_pct, 2)
    details['obv_vs_price_ratio'] = round(obv_change_pct / price_change_pct, 2) if price_change_pct != 0 else 0
    
    if accumulation_signal:
        score += 3
    
    # 3. Price Higher Lows Pattern (3 points)
    higher_lows_score = 0
    periods = [10, 20, 30]  # Check 10, 20, and 30-day periods
    
    for period in periods:
        if len(daily_data) >= period * 2:
            current_low = daily_data['Low'].iloc[-period:].min()
            previous_low = daily_data['Low'].iloc[-period*2:-period].min()
            
            higher_low = current_low > previous_low
            details[f'price_higher_low_{period}d'] = higher_low
            details[f'current_low_{period}d'] = round(current_low, 2)
            details[f'previous_low_{period}d'] = round(previous_low, 2)
            
            if higher_low:
                higher_lows_score += 1
    
    price_higher_lows_confirmed = higher_lows_score >= 2
    details['price_higher_lows_confirmed'] = price_higher_lows_confirmed
    details['higher_lows_count'] = higher_lows_score
    
    if price_higher_lows_confirmed:
        score += 3
    
    # 4. OBV Higher High Detection (1 point)
    if len(obv) >= 40:
        current_obv_high = obv.iloc[-20:].max()  # Recent 20-day OBV high
        previous_obv_high = obv.iloc[-40:-20].max()  # Previous 20-day OBV high
        
        obv_higher_high = current_obv_high > previous_obv_high
        details['obv_higher_high'] = obv_higher_high
        details['current_obv_high'] = round(current_obv_high, 0)
        details['previous_obv_high'] = round(previous_obv_high, 0)
        
        if obv_higher_high:
            score += 1
            
            # 5. Price Divergence Detection (4 points)
            current_price_high = daily_data['High'].iloc[-20:].max()
            previous_price_high = daily_data['High'].iloc[-40:-20].max()
            
            price_higher_high = current_price_high > previous_price_high
            price_divergence = obv_higher_high and not price_higher_high
            
            details['price_higher_high'] = price_higher_high
            details['current_price_high'] = round(current_price_high, 2)
            details['previous_price_high'] = round(previous_price_high, 2)
            details['price_divergence'] = price_divergence
            
            if price_divergence:
                score += 4
        else:
            details['obv_higher_high'] = False
            details['price_divergence'] = False
    else:
        details['obv_higher_high'] = False
        details['price_divergence'] = False
    
    # 6. OBV Short-term vs Long-term MA alignment (informational only)
    obv_ma_alignment = obv_ma10.iloc[-1] > obv_ma21.iloc[-1] if len(obv_ma10) > 0 and len(obv_ma21) > 0 else False
    details['obv_ma_alignment'] = obv_ma_alignment
    
    obv_analysis_confirmed = score >= 3
    return obv_analysis_confirmed, score, details

def check_trend_template(daily_data):
    """Check Mark Minervini's 10-point Trend Template"""
    if len(daily_data) < 200:
        return False, 0, {}
    
    latest = daily_data.iloc[-1]
    details = {}
    score = 0
    criteria_met = 0
    
    # 1. Price above 50-day MA
    price_above_ma50 = latest['Close'] > latest['MA50']
    details['price_above_ma50'] = price_above_ma50
    if price_above_ma50:
        criteria_met += 1
        score += 1
    
    # 2. Price above 150-day MA
    price_above_ma150 = latest['Close'] > latest['MA150']
    details['price_above_ma150'] = price_above_ma150
    if price_above_ma150:
        criteria_met += 1
        score += 1
    
    # 3. Price above 200-day MA
    price_above_ma200 = latest['Close'] > latest['MA200']
    details['price_above_ma200'] = price_above_ma200
    if price_above_ma200:
        criteria_met += 1
        score += 1
    
    # 4. 50-day MA above 150-day MA
    ma50_above_ma150 = latest['MA50'] > latest['MA150']
    details['ma50_above_ma150'] = ma50_above_ma150
    if ma50_above_ma150:
        criteria_met += 1
        score += 1
    
    # 5. 50-day MA above 200-day MA
    ma50_above_ma200 = latest['MA50'] > latest['MA200']
    details['ma50_above_ma200'] = ma50_above_ma200
    if ma50_above_ma200:
        criteria_met += 1
        score += 1
    
    # 6. 150-day MA above 200-day MA
    ma150_above_ma200 = latest['MA150'] > latest['MA200']
    details['ma150_above_ma200'] = ma150_above_ma200
    if ma150_above_ma200:
        criteria_met += 1
        score += 1
    
    # 7. 200-day MA is rising
    ma200_current = latest['MA200']
    ma200_30_days_ago = daily_data.iloc[-30]['MA200'] if len(daily_data) >= 30 else ma200_current
    ma200_rising = ma200_current > ma200_30_days_ago
    details['ma200_rising'] = ma200_rising
    if ma200_rising:
        criteria_met += 1
        score += 1
    
    # 8. Price within 25% of 52-week high
    high_52w = daily_data['High'].rolling(window=252).max().iloc[-1]
    distance_from_high = (high_52w - latest['Close']) / high_52w * 100
    within_25pct_high = distance_from_high <= 25
    details['within_25pct_high'] = within_25pct_high
    details['distance_from_52w_high'] = round(distance_from_high, 2)
    if within_25pct_high:
        criteria_met += 1
        score += 1
    
    # 9. Price above 30% above 52-week low
    low_52w = daily_data['Low'].rolling(window=252).min().iloc[-1]
    above_52w_low_pct = (latest['Close'] - low_52w) / low_52w * 100
    above_30pct_low = above_52w_low_pct >= 30
    details['above_30pct_52w_low'] = above_30pct_low
    details['above_52w_low_pct'] = round(above_52w_low_pct, 2)
    if above_30pct_low:
        criteria_met += 1
        score += 1
    
    # 10. Relative strength (simplified - price performance vs market)
    if len(daily_data) >= 63:
        price_3m_ago = daily_data['Close'].iloc[-63]
        price_performance = (latest['Close'] - price_3m_ago) / price_3m_ago * 100
        relative_strength_good = price_performance > 0  # Simplified: positive 3-month performance
        details['relative_strength'] = relative_strength_good
        details['price_performance_3m'] = round(price_performance, 2)
        if relative_strength_good:
            criteria_met += 1
            score += 1
    
    details['criteria_met'] = criteria_met
    details['total_criteria'] = 10
    
    # UPDATED: Quantitative scoring - score equals criteria_met (1 point per rule)
    score = criteria_met
    trend_template_met = True  # always allow further analysis
    
    # Stage 2 identification (stricter criteria)
    stage2_criteria = 0
    if price_above_ma50 and price_above_ma150 and price_above_ma200:
        stage2_criteria += 1
    if ma50_above_ma150 and ma150_above_ma200:
        stage2_criteria += 1
    if ma200_rising:
        stage2_criteria += 1
    if within_25pct_high:
        stage2_criteria += 1
    if above_30pct_low:
        stage2_criteria += 1
    if relative_strength_good:
        stage2_criteria += 1
    
    is_stage2 = stage2_criteria >= 6
    details['is_stage2'] = is_stage2
    details['stage2_criteria_met'] = stage2_criteria
    
    return trend_template_met, score, details

def check_uptrend_nearing_breakout(daily_data, weekly_data):
    """Check if stock is in uptrend nearing breakout"""
    if len(daily_data) < 100:
        return False, 0, {}
    
    details = {}
    score = 0
    current_price = daily_data['Close'].iloc[-1]
    
    # 1. Current high equals 100-day high within last 10 candles
    high_100_day = daily_data['High_100'].iloc[-1]
    recent_10_high = daily_data['High'].iloc[-10:].max()
    near_100day_high = recent_10_high >= high_100_day * 0.99  # Within 1% tolerance
    details['near_100day_high'] = near_100day_high
    details['high_100_day'] = round(high_100_day, 2)
    details['recent_10_high'] = round(recent_10_high, 2)
    if near_100day_high:
        score += 2
    
    # 2. Current price within 7% of daily 100-day high
    distance_to_daily_high = (high_100_day - current_price) / current_price * 100
    within_7pct_daily = distance_to_daily_high <= 7.0
    details['within_7pct_daily_high'] = within_7pct_daily
    details['distance_to_daily_high'] = round(distance_to_daily_high, 2)
    if within_7pct_daily:
        score += 2
    
    # 3. Current price within 20% of weekly 100-period high
    if len(weekly_data) >= 100:
        weekly_100_high = weekly_data['High_100'].iloc[-1]
        distance_to_weekly_high = (weekly_100_high - current_price) / current_price * 100
        within_20pct_weekly = distance_to_weekly_high <= 20.0
        details['within_20pct_weekly_high'] = within_20pct_weekly
        details['distance_to_weekly_high'] = round(distance_to_weekly_high, 2)
        details['weekly_100_high'] = round(weekly_100_high, 2)
        if within_20pct_weekly:
            score += 1
    
    # 4. Current price below daily high (not broken out yet)
    below_daily_high = current_price <= high_100_day
    details['below_daily_high'] = below_daily_high
    if below_daily_high:
        score += 1
    
    # 5. Graduated ATR-based recent breakout penalty
    if len(daily_data) >= 20:
        price_5_days_ago = daily_data['Close'].iloc[-6]
        price_change_5d = current_price - price_5_days_ago
        price_change_5d_pct = (price_change_5d / price_5_days_ago) * 100
        
        current_atr = daily_data['ATR14'].iloc[-1]
        atr_as_pct = (current_atr / current_price) * 100
        
        atr_multiple = price_change_5d / current_atr if current_atr > 0 else 0
        
        penalty = 0
        penalty_reason = "No penalty"
        already_broken_out = False
        
        if atr_multiple >= 2.5:
            penalty = min(score, 3)
            penalty_reason = f"Strong breakout (≥2.5x ATR: {atr_multiple:.1f}x)"
            already_broken_out = True
        elif atr_multiple >= 2.0:
            penalty = min(score, 2)
            penalty_reason = f"Moderate breakout (2.0-2.5x ATR: {atr_multiple:.1f}x)"
            already_broken_out = True
        elif atr_multiple >= 1.5:
            penalty = min(score, 1)
            penalty_reason = f"Mild breakout (1.5-2.0x ATR: {atr_multiple:.1f}x)"
            already_broken_out = True
        
        score -= penalty
        
        details['already_broken_out'] = already_broken_out
        details['price_5_days_ago'] = round(price_5_days_ago, 2)
        details['price_change_5d_pct'] = round(price_change_5d_pct, 2)
        details['price_change_5d_abs'] = round(price_change_5d, 2)
        details['current_atr'] = round(current_atr, 2)
        details['atr_as_pct'] = round(atr_as_pct, 2)
        details['atr_multiple'] = round(atr_multiple, 2)
        details['breakout_penalty'] = penalty
        details['penalty_reason'] = penalty_reason
        
        details['atr_breakout_threshold'] = round(1.5 * current_atr, 2)
        details['atr_threshold_pct'] = round((1.5 * current_atr / current_price) * 100, 2)
        
    else:
        details['already_broken_out'] = False
        details['price_change_5d_pct'] = 0
        details['breakout_penalty'] = 0
        details['current_atr'] = 0
        details['atr_as_pct'] = 0
        details['atr_multiple'] = 0
        details['penalty_reason'] = "Insufficient data"
    
    breakout_ready = score >= 4
    return breakout_ready, score, details

def check_higher_lows(daily_data):
    """Check for higher lows pattern"""
    if len(daily_data) < 50:
        return False, 0, {}
    
    details = {}
    score = 0
    periods = ENHANCED_VCP_OBV_CONFIG['higher_lows_periods']
    
    for period in periods:
        if len(daily_data) >= period * 2:
            current_low = daily_data['Low'].iloc[-period:].min()
            previous_low = daily_data['Low'].iloc[-period*2:-period].min()
            
            higher_low = current_low > previous_low
            details[f'higher_low_{period}d'] = higher_low
            details[f'current_low_{period}d'] = round(current_low, 2)
            details[f'previous_low_{period}d'] = round(previous_low, 2)
            
            if higher_low:
                score += 1
    
    higher_lows_confirmed = score >= 2
    return higher_lows_confirmed, score, details

def check_volume_contracting(daily_data):
    """Check for volume contraction pattern"""
    if len(daily_data) < 50:
        return False, 0, {}
    
    details = {}
    score = 0
    periods = ENHANCED_VCP_OBV_CONFIG['volume_contraction_periods']
    
    current_volume_ma = daily_data['Volume_MA20'].iloc[-1]
    
    contracting_count = 0
    for period in periods:
        if len(daily_data) >= period + 1:
            past_volume_ma = daily_data['Volume_MA20'].iloc[-(period+1)]
            volume_contracting = current_volume_ma < past_volume_ma
            
            details[f'volume_contracting_{period}d'] = volume_contracting
            details[f'current_volume_ma'] = round(current_volume_ma, 0)
            details[f'volume_ma_{period}d_ago'] = round(past_volume_ma, 0)
            
            if volume_contracting:
                contracting_count += 1
    
    volume_contracting_confirmed = contracting_count >= 3
    details['contracting_signals'] = contracting_count
    details['total_signals'] = len(periods)
    
    if volume_contracting_confirmed:
        score = contracting_count
    
    return volume_contracting_confirmed, score, details

# ==================== NEW: EXTENSION / LATE BREAKOUT FILTER ====================

def add_extension_and_breakout_filters(daily_data, settings=None):
    """
    Mark late-stage / already-extended breakouts so we can drop them.

    Rules (hard filter, no score):
    1) > +20% in last 10 days      -> extended_roc
    2) > +8% above 20-day MA       -> extended_ma20
    3) Wide-range bar + big volume -> climactic_recent
    4) Breakout age > 1 day above 40-day pivot -> extended_breakout_age
    """
    cfg = {
        "roc_lookback": 10,
        "roc_max": 0.20,           # 20% in 10 days
        "ma_dist_max": 0.08,       # 8% above MA20
        "wrb_atr_len": 20,
        "wrb_mult": 2.0,           # TR > 2x ATR20
        "vol_mult": 1.5,           # Volume > 1.5x 20d avg
        "climactic_lookback": 3,   # treat last 3 bars as extended after WRB
        "breakout_base_len": 40,   # pivot = 40-day high close
        "breakout_buffer": 0.01,   # >1% over pivot = breakout
        "breakout_max_age": 1      # only day 0–1 after breakout are allowed
    }
    if settings:
        cfg.update(settings)

    # 1) recent rate of change
    lb = cfg["roc_lookback"]
    daily_data[f"roc_{lb}d"] = daily_data["Close"].pct_change(lb)
    daily_data["extended_roc"] = daily_data[f"roc_{lb}d"] > cfg["roc_max"]

    # 2) distance from 20-day MA
    daily_data["dist_ma20"] = (daily_data["Close"] - daily_data["MA20"]) / daily_data["MA20"]
    daily_data["extended_ma20"] = daily_data["dist_ma20"] > cfg["ma_dist_max"]

    # 3) climactic wide-range bar on big volume
    daily_data["ATR20_ext"] = daily_data["TR"].rolling(cfg["wrb_atr_len"]).mean()
    daily_data["wrb_mult"] = daily_data["TR"] / daily_data["ATR20_ext"]
    daily_data["vol_mult_ext"] = daily_data["Volume"] / daily_data["Volume_MA20"]

    daily_data["climactic_bar"] = (
        (daily_data["wrb_mult"] > cfg["wrb_mult"]) &
        (daily_data["vol_mult_ext"] > cfg["vol_mult"])
    )
    daily_data["climactic_recent"] = (
        daily_data["climactic_bar"]
        .rolling(cfg["climactic_lookback"])
        .max()
        .astype(bool)
    )

    # 4) breakout age above 40-day pivot
    base_len = cfg["breakout_base_len"]
    pivot = daily_data["Close"].rolling(base_len).max().shift(1)
    broke_out = daily_data["Close"] > pivot * (1 + cfg["breakout_buffer"])

    grp = (broke_out != broke_out.shift(1)).cumsum()
    age = broke_out.groupby(grp).cumsum() - 1
    daily_data["breakout_age"] = np.where(broke_out, age, np.nan)

    latest = daily_data.iloc[-1]

    extended_roc = bool(latest.get("extended_roc", False))
    extended_ma20 = bool(latest.get("extended_ma20", False))
    climactic_recent = bool(latest.get("climactic_recent", False))
    breakout_age = latest.get("breakout_age", np.nan)
    extended_breakout_age = (not pd.isna(breakout_age)) and (
        breakout_age > cfg["breakout_max_age"]
    )

    is_extended = (
        extended_roc
        or extended_ma20
        or climactic_recent
        or extended_breakout_age
    )

    details = {
        "extended_roc": extended_roc,
        "extended_ma20": extended_ma20,
        "climactic_recent": climactic_recent,
        "breakout_age": float(breakout_age) if not pd.isna(breakout_age) else None,
        "extended_breakout_age": extended_breakout_age,
        "pass_filter": not is_extended,
    }

    return not is_extended, details, daily_data

# ======================== MAIN SCAN LOGIC ========================

def enhanced_vcp_obv_scan(symbol):
    """Enhanced VCP pattern detection with OBV analysis (40-point system)"""
    try:
        # Get market cap first
        market_cap = get_market_cap(symbol)
        if market_cap < ENHANCED_VCP_OBV_CONFIG['market_cap_min']:
            return None
        
        # Get basic data (without OBV calculations for speed)
        daily_data, weekly_data = get_enhanced_stock_data_basic(symbol)
        if daily_data is None:
            return None

        # NEW: remove extended / late-stage breakouts (FSM-type already-ran names)
        extension_ok, extension_details, daily_data = add_extension_and_breakout_filters(daily_data)
        if not extension_ok:
            return None
        
        # 1. Trend Template (0-10)
        trend_template_met, trend_score, trend_details = check_trend_template(daily_data)
        
        # 2. Uptrend Nearing Breakout (0-7)
        breakout_ready, breakout_score, breakout_details = check_uptrend_nearing_breakout(daily_data, weekly_data)
        
        # 3. Higher Lows (0-3)
        higher_lows_ok, higher_lows_score, higher_lows_details = check_higher_lows(daily_data)
        
        # 4. Volume Contracting (0-6)
        volume_contracting_ok, volume_score, volume_details = check_volume_contracting(daily_data)
        
        preliminary_score = trend_score + breakout_score + higher_lows_score + volume_score
        
        # 5. OBV Analysis (0-14), only if promising
        if preliminary_score >= 15:
            daily_data = add_obv_calculations(daily_data)
            obv_confirmed, obv_score, obv_details = check_obv_trend_analysis(daily_data)
        else:
            obv_confirmed, obv_score, obv_details = False, 0, {}
        
        total_score = trend_score + breakout_score + higher_lows_score + volume_score + obv_score
        
        is_stage2 = trend_details.get('is_stage2', False)
        
        if is_stage2 and total_score >= 29:
            vcp_category = "🚀 Stage2 & VCP+OBV"
        elif is_stage2 and total_score >= 26:
            vcp_category = "Stage2 & VCP+OBV"
        elif total_score >= 29:
            vcp_category = "🔥 VCP+OBV"
        elif total_score >= 26:
            vcp_category = "VCP+OBV"
        else:
            vcp_category = "📋 low score stock"
        
        result = {
            "symbol": symbol,
            "market_cap": market_cap,
            "market_cap_billions": round(market_cap / 1_000_000_000, 2),
            "total_score": total_score,
            "max_score": 40,
            "vcp_category": vcp_category,
            "current_price": round(daily_data['Close'].iloc[-1], 2),
            "price_change_pct": round((daily_data['Close'].iloc[-1] / daily_data['Close'].iloc[-2] - 1) * 100, 2),
            "criteria_met": {
                "trend_template": trend_template_met,
                "breakout_ready": breakout_ready,
                "higher_lows": higher_lows_ok,
                "volume_contracting": volume_contracting_ok,
                "obv_confirmed": obv_confirmed
            },
            "component_scores": {
                "trend_score": trend_score,
                "breakout_score": breakout_score,
                "higher_lows_score": higher_lows_score,
                "volume_score": volume_score,
                "obv_score": obv_score
            },
            "analysis_details": {
                "trend_template": trend_details,
                "breakout": breakout_details,
                "higher_lows": higher_lows_details,
                "volume": volume_details,
                "obv_analysis": obv_details,
                "extension_filter": extension_details,  # NEW
            }
        }
        
        return result
        
    except Exception as e:
        print(f"分析 {symbol} 增强VCP+OBV模式时出错: {e}")
        return None

def main():
    """Main function for enhanced VCP+OBV scanning"""
    print("🎯 增强VCP+OBV (Volatility Contraction Pattern + On-Balance Volume) 检测器")
    print("基于Mark Minervini趋势模板 + OBV 21日移动平均线分析")
    print("=" * 70)
    
    # Scan options
    print("请选择扫描范围:")
    print("1. 测试模式 (first 25 stock)")
    print("2. 完整扫描 (full 1000+ scan)")
    print("3. 自定义股票列表")
    
    choice = input("请输入选择 (1-3): ").strip()
    
    if choice == "1":
        symbols = STOCK_SYMBOLS[:25]
        print(f"🧪 测试模式: 扫描前25个股票")
    elif choice == "2":
        symbols = STOCK_SYMBOLS
        print(f"🔍 完整扫描: 扫描{len(STOCK_SYMBOLS)}个股票")
    elif choice == "3":
        custom_symbols = input("请输入股票代码 (用逗号分隔): ").strip().upper().split(',')
        symbols = [s.strip() for s in custom_symbols if s.strip()]
        print(f"📝 自定义扫描: {len(symbols)}个股票")
    else:
        print("❌ 无效选择，使用测试模式")
        symbols = STOCK_SYMBOLS[:25]
    
    # Set minimum score
    min_score_input = input("请输入最低评分 (默认21分): ").strip()
    min_score = int(min_score_input) if min_score_input.isdigit() else 21
    
    # Start scanning
    print(f"\n🎯 US Stock VCP Pattern + OBV scan")
    print(f"   - 扫描股票数量: {len(symbols)}")
    print(f"   - 最低评分: {min_score}/40")
    print(f"   - market cap: ≥$100M")
    print(f"   - OBV分析: 21日均线趋势 + 累积信号 + 更高低点")
    print(f"   - Press Ctrl+C gracefully stop")
    print("=" * 70)
    
    results = []
    processed = 0
    errors = 0
    start_time = datetime.now()
    
    for i, symbol in enumerate(symbols):
        try:
            if scan_interrupted:
                print(f"\n🛑 扫描已中断! 已处理 {processed} 个股票")
                print(f"   - 发现模式: {len(results)}")
                print(f"   - 将显示已处理的结果...")
                break
            
            if (i + 1) % 25 == 0 or (i + 1) == len(symbols):
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(symbols) - i - 1) / rate if rate > 0 else 0
                print(f"📈 进度: {i + 1}/{len(symbols)} ({(i + 1)/len(symbols)*100:.1f}%) | "
                      f"发现VCP+OBV: {len(results)} | 错误: {errors} | "
                      f"预计剩余: {eta/60:.1f}分钟")
            
            result = enhanced_vcp_obv_scan(symbol)
            processed += 1
            
            if result and result['total_score'] >= min_score:
                results.append(result)
                
                category = result['vcp_category']
                score = result['total_score']
                
                show_pattern = score >= 21
                
                if show_pattern:
                    price = result['current_price']
                    change = result['price_change_pct']
                    market_cap_b = result['market_cap_billions']
                    
                    scores = result['component_scores']
                    details = result['analysis_details']
                    
                    is_stage2 = details['trend_template'].get('is_stage2', False)
                    stage2_indicator = " [Stage2+OBV]" if is_stage2 else ""
                    
                    print(f"\n{category}: {symbol} | 总分:{score}/40 | ${price} ({change:+.1f}%) | 市值${market_cap_b:.1f}B{stage2_indicator}")
                    
                    if score >= 28:
                        print(f"   📊 评分详情: 趋势{scores['trend_score']}/10 + 突破{scores['breakout_score']}/7 + 低点{scores['higher_lows_score']}/3 + 成交量{scores['volume_score']}/6 + OBV{scores['obv_score']}/14")
                        
                        obv_details = details['obv_analysis']
                        obv_status = []
                        obv_status.append("✅OBV21日MA上升" if obv_details.get('obv_ma21_trending_up') else "❌OBV21日MA上升")
                        obv_status.append("✅累积信号" if obv_details.get('accumulation_signal') else "❌OBV accumlation")
                        obv_status.append("✅价格更高低点" if obv_details.get('price_higher_lows_confirmed') else "❌higher low")
                        obv_status.append("✅OBV更高高点" if obv_details.get('obv_higher_high') else "❌OBV higher high")
                        obv_status.append("✅价格背离" if obv_details.get('price_divergence') else "❌OBV & price bullish diveragence")
                        print(f"   📊 OBV分析({scores['obv_score']}/14): {' '.join(obv_status)} | OBV变化:{obv_details.get('obv_change_21d_pct', 0):.1f}% vs 价格:{obv_details.get('price_change_21d_pct', 0):.1f}%")
            
            time.sleep(0.1)
            
        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"❌ {symbol} 分析失败: {e}")
    
    results.sort(key=lambda x: x['total_score'], reverse=True)
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    status = "中断" if scan_interrupted else "完成"
    print(f"\n📊 扫描{status}统计:")
    print(f"   - 处理股票: {processed}")
    print(f"   - 发现增强VCP+OBV: {len(results)}")
    print(f"   - 错误数量: {errors}")
    print(f"   - 总用时: {total_time/60:.1f}分钟")
    print(f"   - 平均速度: {processed/(total_time/60):.1f}个/分钟")
    print(f"   - 增强VCP+OBV发现率: {len(results)/processed*100:.2f}%")
    if scan_interrupted:
        print(f"   - 剩余未处理: {len(symbols) - processed} 个股票")
    
    if results:
        print(f"\n🏆 发现的增强VCP+OBV模式 (按评分排序):")
        print("=" * 90)
        for i, result in enumerate(results[:15]):
            category = result['vcp_category']
            symbol = result['symbol']
            score = result['total_score']
            price = result['current_price']
            change = result['price_change_pct']
            market_cap_b = result['market_cap_billions']
            obv_score = result['component_scores']['obv_score']
            print(f"{i+1:2d}. {category} {symbol:>6} | {score:2d}/40分 | ${price:>8.2f} ({change:+6.1f}%) | ${market_cap_b:.1f}B | OBV:{obv_score}/14")
    else:
        print("❌ 未发现符合条件的增强VCP+OBV模式")

if __name__ == "__main__":
    main()