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
for s in symbols:
    try:
        df = get_stock_data(s)
        if df is None:
            print(f"{s} 数据不足，跳过")
            continue
        score, rsi, vol_ratio = score_stock(df)
        close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])
        change = (close / prev_close - 1.0) * 100.0
        if score >= 70:
            results.append({
                "股票代码": s,
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

if df_result.empty:
    print("暂无满足条件（评分≥70）的标的，将导出空模板。")
    strong_buy = pd.DataFrame(columns=["股票代码","收盘价","涨跌幅 %","RSI","成交量/均量比","策略评分","评级"])
    buy = strong_buy.copy()
    industry_summary = pd.DataFrame(columns=["评级","count","mean"])
else:
    df_result = df_result.sort_values(by="策略评分", ascending=False)
    # 拆分两个Sheet
    strong_buy = df_result[df_result["策略评分"] >= 85]
    buy = df_result[(df_result["策略评分"] >= 70) & (df_result["策略评分"] < 85)]
    # 汇总
    industry_summary = df_result.groupby("评级")["策略评分"].agg(["count", "mean"]).reset_index()

# 导出 Excel
with pd.ExcelWriter(OUTPUT_PATH) as writer:
    strong_buy.to_excel(writer, sheet_name="⭐Strong Buy", index=False)
    buy.to_excel(writer, sheet_name="✅Buy", index=False)
    industry_summary.to_excel(writer, sheet_name="Industry Summary", index=False)

print(f"✅ 扫描完成，文件已生成：{OUTPUT_PATH}")
