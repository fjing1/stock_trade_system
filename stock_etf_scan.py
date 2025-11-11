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

# ============ 参数设置 ============
symbols = ["AAPL", "MSFT", "META", "NVDA", "AMD", "GOOGL", "CSCO",
           "FCX", "HIMS", "LITE", "MU", "AVGO", "NUE", "CRWD", "TSLA", "SMCI"]

# 新增 ETF 列表
etf_symbols = ["SPY", "QQQ", "IWM"]

# 合并为总扫描列表（不重复）
symbols_all = list(dict.fromkeys(symbols + etf_symbols))


OUTPUT_PATH = f"US_StrongBuy_Scan_{datetime.now().strftime('%Y%m%d')}.xlsx"


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
def get_stock_data(symbol):
    # 显式设置 auto_adjust=False，避免不同版本行为差异
    data = yf.download(symbol, period="3mo", interval="1d",
                       auto_adjust=False, progress=False)

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
    # 统一取“最后一行”的各字段为标量，避免 Series 间比较
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

    # 返回评分、RSI、量比（四舍五入）
    rsi_out = (None if pd.isna(rsi) else round(rsi, 1))
    volr_out = (None if pd.isna(vol_ratio) else round(vol_ratio, 2))
    return round(score, 1), rsi_out, volr_out


# ============ 主逻辑 ============
results = []
etf_overview_rows = []

for s in symbols_all:
    try:
        df = get_stock_data(s)
        if df is None:
            print(f"{s} 数据不足，跳过")
            continue

        # 无论是否达标，若是ETF就先记录一个概览快照
        if s in etf_symbols:
            try:
                etf_overview_rows.append(build_etf_overview(df, s))
            except Exception as e_snap:
                print(f"{s} ETF概览生成失败: {e_snap}")

        # 评分与选股
        score, rsi, vol_ratio = score_stock(df)
        close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])
        change = (close / prev_close - 1.0) * 100.0
        if score >= 70:
            results.append({
                "类别": ("ETF" if s in etf_symbols else "股票"),
                "代码": s,
                "收盘价": round(close, 2),
                "涨跌幅 %": round(change, 2),
                "RSI": rsi,
                "成交量/均量比": vol_ratio,
                "策略评分": score,
                "评级": "⭐ 强买入" if score >= 85 else "✅ 买入"
            })

    except Exception as e:
        print(f"{s} 错误: {e}")


# 转换为 DataFrame（允许为空）
df_result = pd.DataFrame(results)
df_etf_overview = pd.DataFrame(etf_overview_rows)

# 准备空模板
empty_cols_pick = ["类别","代码","收盘价","涨跌幅 %","RSI","成交量/均量比","策略评分","评级"]
empty_pick_df = pd.DataFrame(columns=empty_cols_pick)

if df_result.empty:
    print("暂无满足条件（评分≥70）的标的，将导出空模板。")
    df_result_sorted = empty_pick_df.copy()
else:
    df_result_sorted = df_result.sort_values(by="策略评分", ascending=False)

# 按类别拆分
stock_df = df_result_sorted[df_result_sorted["类别"] == "股票"]
etf_df   = df_result_sorted[df_result_sorted["类别"] == "ETF"]

# 各自拆分强买/买入
def split_tables(sub_df):
    strong_buy = sub_df[sub_df["策略评分"] >= 85]
    buy = sub_df[(sub_df["策略评分"] >= 70) & (sub_df["策略评分"] < 85)]
    return strong_buy, buy

stock_strong, stock_buy = split_tables(stock_df) if not stock_df.empty else (empty_pick_df.copy(), empty_pick_df.copy())
etf_strong, etf_buy     = split_tables(etf_df) if not etf_df.empty else (empty_pick_df.copy(), empty_pick_df.copy())

# 汇总（基于全部结果而非单类）
if df_result_sorted.empty:
    industry_summary = pd.DataFrame(columns=["评级","count","mean"])
else:
    industry_summary = df_result_sorted.groupby("评级")["策略评分"].agg(["count", "mean"]).reset_index()

# 导出 Excel
with pd.ExcelWriter(OUTPUT_PATH) as writer:
    stock_strong.to_excel(writer, sheet_name="Stock ⭐Strong Buy", index=False)
    stock_buy.to_excel(writer, sheet_name="Stock ✅Buy", index=False)
    etf_strong.to_excel(writer, sheet_name="ETF ⭐Strong Buy", index=False)
    etf_buy.to_excel(writer, sheet_name="ETF ✅Buy", index=False)
    industry_summary.to_excel(writer, sheet_name="Industry Summary", index=False)

    # ETF总览（永远输出），按你喜好可再排序一下
    if not df_etf_overview.empty:
        # 示例：按“MACD>Signal”“站上MA50”“站上MA20”进行权重排序
        sort_cols = ["MACD>Signal","站上MA50","站上MA20","MA50上升","MA20上升"]
        for c in sort_cols:
            if c in df_etf_overview.columns:
                df_etf_overview[c] = df_etf_overview[c].astype("boolean")
        df_etf_overview.to_excel(writer, sheet_name="ETF Overview", index=False)
    else:
        pd.DataFrame(columns=["ETF","收盘价","RSI","站上MA20","站上MA50","MACD>Signal","MA20上升","MA50上升","与MA20偏离%","与MA50偏离%"])\
          .to_excel(writer, sheet_name="ETF Overview", index=False)

print(f"✅ 扫描完成，文件已生成：{OUTPUT_PATH}")

