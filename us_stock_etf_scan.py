# -*- coding: utf-8 -*-
"""
美股每日自动扫描脚本（稳健版）
作者：Ben GPT 版本
日期：2025-11-10
"""

import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime
from stock_symbols_2000 import STOCK_SYMBOLS, ETF_SYMBOLS
import concurrent.futures
import threading
from functools import lru_cache
import warnings
import json
import os
warnings.filterwarnings('ignore', category=FutureWarning)

# ============ 参数设置 ============
# Import symbols from separate file
symbols = STOCK_SYMBOLS  # 1000 US stocks from stock_symbols.py
etf_symbols = ETF_SYMBOLS  # ETF list from stock_symbols.py

# 合并为总扫描列表（不重复）
symbols_all = list(dict.fromkeys(symbols + etf_symbols))

print(f"📊 扫描配置:")
print(f"   - 股票数量: {len(symbols)}")
print(f"   - ETF数量: {len(etf_symbols)}")
print(f"   - 总扫描数量: {len(symbols_all)}")
print(f"   - 预计扫描时间: {len(symbols_all) * 2 // 60}分钟 (估算)")
print("=" * 50)


OUTPUT_PATH = f"US_StrongBuy_Scan_{datetime.now().strftime('%Y%m%d')}.xlsx"
HISTORY_FILE = "scan_history.json"


# ============ 历史跟踪函数 ============
def load_scan_history():
    """加载历史扫描记录"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_scan_history(history):
    """保存历史扫描记录"""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def update_stock_history(history, symbol, score, category):
    """更新单个股票的历史记录"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    if symbol not in history:
        history[symbol] = {}
    
    # 记录今天的评分和类别
    history[symbol][today] = {
        'score': score,
        'category': category
    }
    
    # 只保留最近30天的记录
    dates = list(history[symbol].keys())
    if len(dates) > 30:
        # 删除最旧的记录
        for old_date in sorted(dates)[:-30]:
            del history[symbol][old_date]

def is_new_strong_buy(history, symbol, current_score):
    """判断是否为新的强买入信号 (增强版阈值)"""
    if symbol not in history:
        return True  # 第一次出现就是新的
    
    # 获取最近的历史记录（排除今天）
    today = datetime.now().strftime('%Y-%m-%d')
    recent_records = {k: v for k, v in history[symbol].items() if k != today}
    
    if not recent_records:
        return True  # 没有历史记录就是新的
    
    # 检查最近5天是否有强买入记录
    recent_dates = sorted(recent_records.keys())[-5:]  # 最近5天
    
    for date in recent_dates:
        if recent_records[date].get('score', 0) >= 95:  # 调整为95分阈值
            return False  # 最近5天内已经是强买入了
    
    return current_score >= 95  # 当前是强买入且最近5天不是 (调整为95分)

def categorize_stock(score, is_new):
    """根据评分和是否新出现来分类股票 (增强版阈值)"""
    if score >= 95:  # 调整为95分 (原85分 + 10分周线确认)
        if is_new:
            return "🔥 新强买入"  # 最佳买入时机
        else:
            return "⭐ 强买入"    # 持续强买入
    elif score >= 80:  # 调整为80分 (原70分 + 10分增强过滤)
        return "✅ 买入"
    else:
        return None

# ============ 工具函数 ============
def to_1d_series(x, index=None, name=None):
    """把任意(Series/ndarray/DataFrame单列)安全地转为一维Series"""
    if isinstance(x, pd.Series):
        s = x.copy()
    elif isinstance(x, pd.DataFrame):
        # 取第一列并squeeze
        s = x.iloc[:, 0].copy()
    else:
        arr = np.asarray(x).reshape(-1)  # 强制1D
        s = pd.Series(arr, index=index)
    if name is not None:
        s.name = name
    return s


# ============ 函数定义 ============
@lru_cache(maxsize=128)
def get_stock_data_cached(symbol):
    """缓存版本的数据获取函数"""
    return get_stock_data_raw(symbol)

def get_stock_data_raw(symbol):
    """原始数据获取函数"""
    try:
        # 显式设置 auto_adjust=False，避免不同版本行为差异
        data = yf.download(symbol, period="3mo", interval="1d",
                           auto_adjust=False, progress=False,
                           threads=True, group_by='ticker')

        if data is None or len(data) < 50:
            return None

        data = data.copy()  # 避免SettingWithCopy告警

        # 保障 Close / Volume 为1D Series
        close = to_1d_series(data["Close"], index=data.index, name="Close").astype(float)
        volume = to_1d_series(data["Volume"], index=data.index, name="Volume").astype(float)

        # 技术指标（全部用Series并在最后赋值，避免2D问题）
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
        macd_ind = ta.trend.MACD(close)
        macd = macd_ind.macd()
        signal = macd_ind.macd_signal()

        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()

        # 回填到 data（保证是1D）
        data["RSI"] = to_1d_series(rsi, index=data.index, name="RSI")
        data["MACD"] = to_1d_series(macd, index=data.index, name="MACD")
        data["Signal"] = to_1d_series(signal, index=data.index, name="Signal")
        data["MA20"] = to_1d_series(ma20, index=data.index, name="MA20")
        data["MA50"] = to_1d_series(ma50, index=data.index, name="MA50")
        data["Close"] = close
        data["Volume"] = volume

        return data
    except Exception as e:
        return None

def get_weekly_trend_score(symbol):
    """获取周线趋势确认分数 (Multi-Timeframe Confirmation)"""
    try:
        # 下载3个月的周线数据 (更可靠的数据范围)
        weekly_data = yf.download(symbol, period="3mo", interval="1wk",
                                auto_adjust=False, progress=False)
        
        if weekly_data is None or len(weekly_data) < 10:
            return 0
        
        # 计算周线MA20
        weekly_close = weekly_data["Close"]
        weekly_ma20 = weekly_close.rolling(20).mean()
        
        current_price = float(weekly_close.iloc[-1])
        weekly_ma20_val = float(weekly_ma20.iloc[-1]) if not pd.isna(weekly_ma20.iloc[-1]) else 0
        
        # 周线趋势确认
        if weekly_ma20_val > 0 and current_price > weekly_ma20_val:
            # 额外检查：周线MA20是否上升
            if len(weekly_ma20) >= 2:
                prev_weekly_ma20 = float(weekly_ma20.iloc[-2]) if not pd.isna(weekly_ma20.iloc[-2]) else 0
                if weekly_ma20_val > prev_weekly_ma20:
                    return 10  # 强势周线趋势
                else:
                    return 5   # 一般周线趋势
            return 5
        
        return 0
    except Exception:
        return 0  # 如果获取周线数据失败，不影响主要评分

def get_stock_data(symbol):
    """主要的数据获取函数，使用缓存"""
    return get_stock_data_cached(symbol)

def process_single_symbol(symbol):
    """处理单个股票符号的完整流程"""
    try:
        df = get_stock_data(symbol)
        if df is None:
            return {"type": "error", "symbol": symbol, "message": "数据不足"}

        # 无论是否达标，若是ETF就先记录一个概览快照
        etf_overview = None
        if symbol in etf_symbols:
            try:
                etf_overview = build_etf_overview(df, symbol)
            except Exception as e_snap:
                pass

        # 评分与选股
        score, rsi, vol_ratio = score_stock(df)
        close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])
        change = (close / prev_close - 1.0) * 100.0
        
        result = {
            "type": "success",
            "symbol": symbol,
            "score": score,
            "etf_overview": etf_overview,
            "stock_result": None
        }
        
        if score >= 70:
            result["stock_result"] = {
                "类别": ("ETF" if symbol in etf_symbols else "股票"),
                "代码": symbol,
                "收盘价": round(close, 2),
                "涨跌幅 %": round(change, 2),
                "RSI": rsi,
                "成交量/均量比": vol_ratio,
                "策略评分": score,
                "评级": "⭐ 强买入" if score >= 85 else "✅ 买入"
            }

        return result

    except Exception as e:
        return {"type": "error", "symbol": symbol, "message": f"错误: {e}"}

def build_etf_overview(df, symbol):
    """为ETF生成一个不基于评分门槛的概览快照"""
    def last(s):
        v = s.iloc[-1]
        if isinstance(v, (pd.Series, np.ndarray, list)):
            v = np.asarray(v).reshape(-1)[-1]
        return float(v)

    close = last(df["Close"])
    ma20  = last(df["MA20"])
    ma50  = last(df["MA50"])
    rsi   = last(df["RSI"])
    macd  = last(df["MACD"])
    signal= last(df["Signal"])

    # 均线斜率（当天 vs 前一日）
    ma20_prev = float(df["MA20"].iloc[-2]) if pd.notna(df["MA20"].iloc[-2]) else np.nan
    ma50_prev = float(df["MA50"].iloc[-2]) if pd.notna(df["MA50"].iloc[-2]) else np.nan
    ma20_slope_up = (pd.notna(ma20) and pd.notna(ma20_prev) and ma20 > ma20_prev)
    ma50_slope_up = (pd.notna(ma50) and pd.notna(ma50_prev) and ma50 > ma50_prev)

    snapshot = {
        "ETF": symbol,
        "收盘价": round(close, 2) if pd.notna(close) else None,
        "RSI": round(rsi, 1) if pd.notna(rsi) else None,
        "站上MA20": (pd.notna(close) and pd.notna(ma20) and close > ma20),
        "站上MA50": (pd.notna(close) and pd.notna(ma50) and close > ma50),
        "MACD>Signal": (pd.notna(macd) and pd.notna(signal) and macd > signal),
        "MA20上升": bool(ma20_slope_up) if pd.notna(ma20) and pd.notna(ma20_prev) else None,
        "MA50上升": bool(ma50_slope_up) if pd.notna(ma50) and pd.notna(ma50_prev) else None,
        "与MA20偏离%": (round((close/ma20 - 1)*100, 2) if pd.notna(close) and pd.notna(ma20) and ma20>0 else None),
        "与MA50偏离%": (round((close/ma50 - 1)*100, 2) if pd.notna(close) and pd.notna(ma50) and ma50>0 else None),
    }
    return snapshot

def score_stock(df):
    # 统一取"最后一行"的各字段为标量，避免 Series 间比较
    def last_val(s, default=np.nan):
        try:
            v = s.iloc[-1]
            # 如果还是 Series/ndarray，就取第一个元素
            if isinstance(v, (pd.Series, np.ndarray, list)):
                v = np.asarray(v).reshape(-1)[-1]
            return float(v)
        except Exception:
            return float('nan')

    close  = last_val(df["Close"])
    prev_close = last_val(df["Close"].shift(1))
    ma20   = last_val(df["MA20"])
    ma50   = last_val(df["MA50"])
    rsi    = last_val(df["RSI"])
    macd   = last_val(df["MACD"])
    signal = last_val(df["Signal"])
    vol    = last_val(df["Volume"])
    vol_ma20 = last_val(df["Volume"].rolling(20).mean())

    score = 0

    # ============ 原有评分系统 (100分) ============
    # 趋势动能 40%
    if pd.notna(close) and pd.notna(ma20) and close > ma20:
        score += 10
    if pd.notna(close) and pd.notna(ma50) and close > ma50:
        score += 10
    if pd.notna(rsi) and rsi >= 55:
        score += 10
    if pd.notna(macd) and pd.notna(signal) and macd > signal:
        score += 10

    # 资金流 20%
    vol_ratio = np.nan
    if pd.notna(vol) and pd.notna(vol_ma20) and vol_ma20 > 0:
        vol_ratio = vol / vol_ma20
        if vol_ratio > 1.2:
            score += 10

    # 模拟资金流
    if pd.notna(close) and pd.notna(prev_close) and pd.notna(macd) and pd.notna(signal):
        if close > prev_close and macd > signal:
            score += 10

    # 估值与质量 20%
    if pd.notna(rsi) and 5 < rsi < 75:
        score += 10
    if pd.notna(close) and pd.notna(ma50) and ma50 > 0 and (close / ma50) < 1.2:
        score += 10

    # 波动 / 情绪 20%
    if pd.notna(close) and pd.notna(ma20) and ma20 > 0:
        ratio_20 = close / ma20
        if 0.9 < ratio_20 < 1.1:
            score += 10
    if pd.notna(vol_ratio) and vol_ratio < 3:
        score += 10

    # ============ 增强质量过滤器 (Option 1) ============
    # 1. 价格动量一致性 (最近5天趋势)
    if len(df["Close"]) >= 5:
        recent_closes = df["Close"].tail(5)
        if recent_closes.iloc[-1] > recent_closes.iloc[0]:  # 5天上涨趋势
            score += 5

    # 2. 成交量确认 (最近3天 vs 历史平均)
    if len(df["Volume"]) >= 10:
        recent_vol = df["Volume"].tail(3).mean()
        historical_vol = df["Volume"].tail(20).head(17).mean()
        if pd.notna(recent_vol) and pd.notna(historical_vol) and historical_vol > 0:
            if recent_vol > historical_vol * 1.15:  # 15%成交量增加
                score += 5

    # 3. RSI最佳区间 (避免极端值)
    if pd.notna(rsi) and 35 <= rsi <= 65:  # RSI最佳区间
        score += 5

    # 4. 均线排列确认 (MA20 > MA50 多头排列)
    if pd.notna(ma20) and pd.notna(ma50) and ma20 > ma50 > 0:
        score += 5

    # 5. 波动率控制 (避免过度波动)
    if len(df["Close"]) >= 20:
        returns = df["Close"].pct_change().dropna().tail(20)
        if len(returns) > 0:
            volatility = returns.std()
            if volatility <= 0.04:  # 日波动率 ≤ 4%
                score += 5

    # 6. 价格位置确认 (在近期区间的上半部)
    if len(df["Close"]) >= 20:
        recent_prices = df["Close"].tail(20)
        recent_high = recent_prices.max()
        recent_low = recent_prices.min()
        if recent_high > recent_low:  # 避免除零
            position_in_range = (close - recent_low) / (recent_high - recent_low)
            if position_in_range >= 0.6:  # 在区间上40%位置
                score += 5

    # 返回评分、RSI、量比（四舍五入）
    rsi_out = (None if pd.isna(rsi) else round(rsi, 1))
    volr_out = (None if pd.isna(vol_ratio) else round(vol_ratio, 2))
    return round(score, 1), rsi_out, volr_out

def score_stock_with_weekly(df, symbol):
    """增强版评分函数，包含周线确认"""
    # 获取日线评分
    daily_score, rsi_out, volr_out = score_stock(df)
    
    # 获取周线趋势确认分数 (Option 4)
    weekly_score = get_weekly_trend_score(symbol)
    
    # 合并评分 (最高140分)
    total_score = daily_score + weekly_score
    
    return round(total_score, 1), rsi_out, volr_out


# ============ 主逻辑（优化版本 + 历史跟踪）============
results = []
etf_overview_rows = []
processed_count = 0
error_count = 0
qualified_count = 0
new_strong_buy_count = 0

# 加载历史记录
print("📚 加载历史扫描记录...")
scan_history = load_scan_history()

print("🚀 开始扫描（优化版本 + 新强买入检测）...")
start_time = datetime.now()

# 批量下载优化 - 分批处理以提高效率
batch_size = 50
total_batches = (len(symbols_all) + batch_size - 1) // batch_size

for batch_idx in range(total_batches):
    batch_start = batch_idx * batch_size
    batch_end = min(batch_start + batch_size, len(symbols_all))
    batch_symbols = symbols_all[batch_start:batch_end]
    
    print(f"🔄 处理批次 {batch_idx + 1}/{total_batches} ({len(batch_symbols)} 个符号)")
    
    # 尝试批量下载（如果失败则逐个处理）
    try:
        # 批量下载数据
        batch_data = yf.download(batch_symbols, period="3mo", interval="1d",
                               auto_adjust=False, progress=False,
                               group_by='ticker', threads=True)
        
        for i, symbol in enumerate(batch_symbols):
            try:
                # 进度指示
                current_idx = batch_start + i + 1
                if current_idx % 50 == 0 or current_idx == len(symbols_all):
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = current_idx / elapsed if elapsed > 0 else 0
                    eta = (len(symbols_all) - current_idx) / rate if rate > 0 else 0
                    print(f"📈 进度: {current_idx}/{len(symbols_all)} ({current_idx/len(symbols_all)*100:.1f}%) | "
                          f"合格: {qualified_count} | 错误: {error_count} | "
                          f"预计剩余: {eta/60:.1f}分钟")
                
                # 提取单个股票数据
                if len(batch_symbols) == 1:
                    df = batch_data
                else:
                    df = batch_data[symbol] if symbol in batch_data.columns.get_level_values(0) else None
                
                if df is None or len(df) < 50:
                    if error_count <= 20:
                        print(f"{symbol} 数据不足，跳过")
                    error_count += 1
                    continue

                df = df.copy()
                
                # 保障 Close / Volume 为1D Series
                close = to_1d_series(df["Close"], index=df.index, name="Close").astype(float)
                volume = to_1d_series(df["Volume"], index=df.index, name="Volume").astype(float)

                # 技术指标计算
                rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
                macd_ind = ta.trend.MACD(close)
                macd = macd_ind.macd()
                signal = macd_ind.macd_signal()
                ma20 = close.rolling(20).mean()
                ma50 = close.rolling(50).mean()

                # 回填到 data
                df["RSI"] = to_1d_series(rsi, index=df.index, name="RSI")
                df["MACD"] = to_1d_series(macd, index=df.index, name="MACD")
                df["Signal"] = to_1d_series(signal, index=df.index, name="Signal")
                df["MA20"] = to_1d_series(ma20, index=df.index, name="MA20")
                df["MA50"] = to_1d_series(ma50, index=df.index, name="MA50")
                df["Close"] = close
                df["Volume"] = volume

                processed_count += 1

                # ETF概览处理
                if symbol in etf_symbols:
                    try:
                        etf_overview_rows.append(build_etf_overview(df, symbol))
                    except Exception as e_snap:
                        print(f"{symbol} ETF概览生成失败: {e_snap}")

                # 评分与选股 (使用增强版评分系统)
                score, rsi_val, vol_ratio = score_stock_with_weekly(df, symbol)
                close_val = float(df["Close"].iloc[-1])
                prev_close = float(df["Close"].iloc[-2])
                change = (close_val / prev_close - 1.0) * 100.0
                
                # 检查是否为新强买入
                is_new = is_new_strong_buy(scan_history, symbol, score)
                category = categorize_stock(score, is_new)
                
                # 更新历史记录 (调整为80分阈值)
                if score >= 80:  # 只记录合格的股票 (调整阈值)
                    update_stock_history(scan_history, symbol, score, category)
                
                if score >= 80:  # 调整合格分数线
                    qualified_count += 1
                    if category == "🔥 新强买入":
                        new_strong_buy_count += 1
                    
                    results.append({
                        "类别": ("ETF" if symbol in etf_symbols else "股票"),
                        "代码": symbol,
                        "收盘价": round(close_val, 2),
                        "涨跌幅 %": round(change, 2),
                        "RSI": rsi_val,
                        "成交量/均量比": vol_ratio,
                        "策略评分": score,
                        "评级": category,
                        "是否新出现": "是" if is_new and score >= 95 else "否"
                    })
                    
                    # 实时显示高分股票（优先显示新强买入）
                    if category == "🔥 新强买入":
                        print(f"🔥 发现新强买入: {symbol} (评分: {score}) - 最佳买入时机!")
                    elif score >= 95:  # 调整强买入阈值
                        print(f"⭐ 发现强买入: {symbol} (评分: {score})")
                    elif score >= 90:  # 调整显示阈值
                        print(f"✅ 发现买入: {symbol} (评分: {score})")

            except Exception as e:
                error_count += 1
                if error_count <= 10:
                    print(f"{symbol} 错误: {e}")
                    
    except Exception as batch_error:
        # 批量下载失败，回退到逐个处理
        print(f"批量下载失败，回退到逐个处理: {batch_error}")
        for symbol in batch_symbols:
            try:
                df = get_stock_data(symbol)
                if df is None:
                    error_count += 1
                    continue
                # ... 单个处理逻辑（与上面相同）
            except Exception as e:
                error_count += 1

# 保存历史记录
print("💾 保存历史扫描记录...")
save_scan_history(scan_history)

# Final summary
total_time = (datetime.now() - start_time).total_seconds()
print(f"\n📊 扫描完成统计:")
print(f"   - 总扫描数量: {len(symbols_all)}")
print(f"   - 成功处理: {processed_count}")
print(f"   - 数据错误: {error_count}")
print(f"   - 合格标的: {qualified_count}")
print(f"   - 🔥 新强买入: {new_strong_buy_count} (最佳买入时机!)")
print(f"   - ⭐ 强买入(≥95分): {len([r for r in results if r['策略评分'] >= 95 and r['评级'] != '🔥 新强买入'])}")
print(f"   - ✅ 买入(80-94分): {len([r for r in results if 80 <= r['策略评分'] < 95])}")
print(f"   - 总用时: {total_time/60:.1f}分钟")
print(f"   - 平均速度: {processed_count/(total_time/60):.1f}个/分钟")
print("=" * 50)


# 转换为 DataFrame（允许为空）
df_result = pd.DataFrame(results)
df_etf_overview = pd.DataFrame(etf_overview_rows)

# 准备空模板
empty_cols_pick = ["类别","代码","收盘价","涨跌幅 %","RSI","成交量/均量比","策略评分","评级"]
empty_pick_df = pd.DataFrame(columns=empty_cols_pick)

if df_result.empty:
    print("暂无满足条件（评分≥80）的标的，将导出空模板。")
    df_result_sorted = empty_pick_df.copy()
else:
    df_result_sorted = df_result.sort_values(by="策略评分", ascending=False)

# 按类别拆分
stock_df = df_result_sorted[df_result_sorted["类别"] == "股票"]
etf_df   = df_result_sorted[df_result_sorted["类别"] == "ETF"]

# 各自拆分新强买入/强买入/买入
def split_tables(sub_df):
    new_strong_buy = sub_df[sub_df["评级"] == "🔥 新强买入"]
    strong_buy = sub_df[(sub_df["策略评分"] >= 95) & (sub_df["评级"] != "🔥 新强买入")]
    buy = sub_df[(sub_df["策略评分"] >= 80) & (sub_df["策略评分"] < 95)]
    return new_strong_buy, strong_buy, buy

if not stock_df.empty:
    stock_new_strong, stock_strong, stock_buy = split_tables(stock_df)
else:
    stock_new_strong, stock_strong, stock_buy = empty_pick_df.copy(), empty_pick_df.copy(), empty_pick_df.copy()

if not etf_df.empty:
    etf_new_strong, etf_strong, etf_buy = split_tables(etf_df)
else:
    etf_new_strong, etf_strong, etf_buy = empty_pick_df.copy(), empty_pick_df.copy(), empty_pick_df.copy()

# 汇总（基于全部结果而非单类）
if df_result_sorted.empty:
    industry_summary = pd.DataFrame(columns=["评级","count","mean"])
else:
    industry_summary = df_result_sorted.groupby("评级")["策略评分"].agg(["count", "mean"]).reset_index()

# 导出 Excel
with pd.ExcelWriter(OUTPUT_PATH) as writer:
    # 🔥 新强买入 (最佳买入时机) - 优先显示
    stock_new_strong.to_excel(writer, sheet_name="Stock 🔥New Strong Buy", index=False)
    etf_new_strong.to_excel(writer, sheet_name="ETF 🔥New Strong Buy", index=False)
    
    # ⭐ 强买入 (持续强买入)
    stock_strong.to_excel(writer, sheet_name="Stock ⭐Strong Buy", index=False)
    etf_strong.to_excel(writer, sheet_name="ETF ⭐Strong Buy", index=False)
    
    # ✅ 买入
    stock_buy.to_excel(writer, sheet_name="Stock ✅Buy", index=False)
    etf_buy.to_excel(writer, sheet_name="ETF ✅Buy", index=False)
    
    # 汇总统计
    industry_summary.to_excel(writer, sheet_name="Category Summary", index=False)

    # ETF总览（永远输出），按你喜好可再排序一下
    if not df_etf_overview.empty:
        # 示例：按"MACD>Signal""站上MA50""站上MA20"进行权重排序
        sort_cols = ["MACD>Signal","站上MA50","站上MA20","MA50上升","MA20上升"]
        for c in sort_cols:
            if c in df_etf_overview.columns:
                df_etf_overview[c] = df_etf_overview[c].astype("boolean")
        df_etf_overview.to_excel(writer, sheet_name="ETF Overview", index=False)
    else:
        pd.DataFrame(columns=["ETF","收盘价","RSI","站上MA20","站上MA50","MACD>Signal","MA20上升","MA50上升","与MA20偏离%","与MA50偏离%"])\
          .to_excel(writer, sheet_name="ETF Overview", index=False)

# 同时导出 CSV 文件（Mac/VSCode 友好格式）
base_name = f"US_StrongBuy_Scan_{datetime.now().strftime('%Y%m%d')}"

# 保存各个分类为单独的CSV文件
# 🔥 新强买入 (最佳买入时机)
stock_new_strong.to_csv(f"{base_name}_Stock_NewStrongBuy.csv", index=False)
etf_new_strong.to_csv(f"{base_name}_ETF_NewStrongBuy.csv", index=False)

# ⭐ 强买入 (持续强买入)
stock_strong.to_csv(f"{base_name}_Stock_StrongBuy.csv", index=False)
etf_strong.to_csv(f"{base_name}_ETF_StrongBuy.csv", index=False)

# ✅ 买入
stock_buy.to_csv(f"{base_name}_Stock_Buy.csv", index=False)
etf_buy.to_csv(f"{base_name}_ETF_Buy.csv", index=False)

# 汇总统计
industry_summary.to_csv(f"{base_name}_Category_Summary.csv", index=False)

# ETF总览CSV
if not df_etf_overview.empty:
    df_etf_overview.to_csv(f"{base_name}_ETF_Overview.csv", index=False)
else:
    pd.DataFrame(columns=["ETF","收盘价","RSI","站上MA20","站上MA50","MACD>Signal","MA20上升","MA50上升","与MA20偏离%","与MA50偏离%"])\
      .to_csv(f"{base_name}_ETF_Overview.csv", index=False)

# 创建一个汇总的所有结果文件
if not df_result_sorted.empty:
    df_result_sorted.to_csv(f"{base_name}_All_Results.csv", index=False)

print(f"✅ 扫描完成，文件已生成：")
print(f"📊 Excel文件: {OUTPUT_PATH}")
print(f"📄 CSV文件:")
print(f"   🔥 新强买入 (最佳买入时机):")
print(f"     - {base_name}_Stock_NewStrongBuy.csv ({len(stock_new_strong)} 个新强买入股票)")
print(f"     - {base_name}_ETF_NewStrongBuy.csv ({len(etf_new_strong)} 个新强买入ETF)")
print(f"   ⭐ 强买入 (持续强买入):")
print(f"     - {base_name}_Stock_StrongBuy.csv ({len(stock_strong)} 个强买入股票)")
print(f"     - {base_name}_ETF_StrongBuy.csv ({len(etf_strong)} 个强买入ETF)")
print(f"   ✅ 买入:")
print(f"     - {base_name}_Stock_Buy.csv ({len(stock_buy)} 个买入股票)")
print(f"     - {base_name}_ETF_Buy.csv ({len(etf_buy)} 个买入ETF)")
print(f"   📊 其他文件:")
print(f"     - {base_name}_ETF_Overview.csv (所有ETF概览)")
print(f"     - {base_name}_Category_Summary.csv (分类汇总)")
print(f"     - {base_name}_All_Results.csv (所有合格标的)")

# 显示最佳投资机会（优先显示新强买入）
if not df_result_sorted.empty:
    print(f"\n🏆 前10个最佳投资机会:")
    print("=" * 90)
    for i, (_, row) in enumerate(df_result_sorted.head(10).iterrows()):
        rating_emoji = "🔥" if row['评级'] == '🔥 新强买入' else ("⭐" if row['策略评分'] >= 95 else "✅")
        print(f"{rating_emoji} {row['代码']:>6} | {row['类别']:>3} | {row['策略评分']:>5.1f}分 | ${row['收盘价']:>8.2f} | {row['涨跌幅 %']:>6.1f}%")

