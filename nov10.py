# -*- coding: utf-8 -*-
"""
美股每日自动扫描脚本（双向版：多头 + 空头 + ETF + OBV）
作者：Ben GPT 版本
日期：2025-11-10
"""

import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime

# ============ 参数设置 ============
# 个股清单（可自行扩展）
stock_symbols = [
    "AAPL", "MSFT", "META", "NVDA", "AMD", "GOOGL", "CSCO",
    "FCX", "HIMS", "LITE", "MU", "AVGO", "NUE", "CRWD", "TSLA", "SMCI"
]

# ETF 清单
etf_symbols = ["SPY", "QQQ", "IWM"]

# 合并为总扫描列表（去重）
symbols_all = list(dict.fromkeys(stock_symbols + etf_symbols))

# 输出文件名（按日期）
OUTPUT_PATH = f"US_StrongBuy_Scan_{datetime.now().strftime('%Y%m%d')}.xlsx"


# ============ 工具函数 ============
def to_1d_series(x, index=None, name=None):
    """把任意(Series/ndarray/DataFrame单列)安全地转为一维Series"""
    if isinstance(x, pd.Series):
        s = x.copy()
    elif isinstance(x, pd.DataFrame):
        s = x.iloc[:, 0].copy()
    else:
        arr = np.asarray(x).reshape(-1)
        s = pd.Series(arr, index=index)
    if name is not None:
        s.name = name
    return s


def last_val(s, default=np.nan):
    """取序列最后一个值为 float 标量；异常或NaN时返回 default"""
    try:
        v = s.iloc[-1]
        if isinstance(v, (pd.Series, np.ndarray, list)):
            v = np.asarray(v).reshape(-1)[-1]
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


# ============ 数据获取与指标计算 ============
def get_stock_data(symbol):
    # 显式 auto_adjust=False，避免不同版本行为差异
    data = yf.download(symbol, period="3mo", interval="1d",
                       auto_adjust=False, progress=False)

    if data is None or len(data) < 50:
        return None

    data = data.copy()  # 避免SettingWithCopy告警

    # 保障 Close / Volume 为1D Series
    close = to_1d_series(data["Close"], index=data.index, name="Close").astype(float)
    volume = to_1d_series(data["Volume"], index=data.index, name="Volume").astype(float)

    # 技术指标
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()

    macd_ind = ta.trend.MACD(close)
    macd = macd_ind.macd()
    signal = macd_ind.macd_signal()

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()

    # === OBV 指标 ===
    obv = ta.volume.OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()
    obv_ma20 = obv.rolling(20).mean()

    # 回填到 data（全部1D）
    data["Close"] = close
    data["Volume"] = volume
    data["RSI"] = to_1d_series(rsi, index=data.index, name="RSI")
    data["MACD"] = to_1d_series(macd, index=data.index, name="MACD")
    data["Signal"] = to_1d_series(signal, index=data.index, name="Signal")
    data["MA20"] = to_1d_series(ma20, index=data.index, name="MA20")
    data["MA50"] = to_1d_series(ma50, index=data.index, name="MA50")
    data["OBV"] = to_1d_series(obv, index=data.index, name="OBV")
    data["OBV_MA20"] = to_1d_series(obv_ma20, index=data.index, name="OBV_MA20")

    return data


# ============ 评分函数（多头 / 空头） ============
def score_long(df):
    """多头评分：趋势、动能、量能、OBV、估值/质量、波动/情绪，共100分"""
    close = last_val(df["Close"])
    prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else np.nan
    ma20 = last_val(df["MA20"])
    ma50 = last_val(df["MA50"])
    rsi = last_val(df["RSI"])
    macd = last_val(df["MACD"])
    signal = last_val(df["Signal"])
    vol = last_val(df["Volume"])
    vol_ma20 = last_val(df["Volume"].rolling(20).mean())
    obv = last_val(df["OBV"])
    obv_prev = float(df["OBV"].iloc[-2]) if len(df) >= 2 and pd.notna(df["OBV"].iloc[-2]) else np.nan
    obv_ma20 = last_val(df["OBV_MA20"])

    score = 0

    # 趋势动能 40%
    if pd.notna(close) and pd.notna(ma20) and close > ma20: score += 10
    if pd.notna(close) and pd.notna(ma50) and close > ma50: score += 10
    if pd.notna(rsi) and rsi >= 55: score += 10
    if pd.notna(macd) and pd.notna(signal) and macd > signal: score += 10

    # 资金流 20%
    # 1) 量比
    vol_ratio = np.nan
    if pd.notna(vol) and pd.notna(vol_ma20) and vol_ma20 > 0:
        vol_ratio = vol / vol_ma20
        if vol_ratio > 1.2:
            score += 10
    # 2) OBV 趋势 + 相对位置
    if pd.notna(obv) and pd.notna(obv_prev) and pd.notna(obv_ma20):
        if obv > obv_prev and obv > obv_ma20:
            score += 10

    # 估值与质量 20%（中性防过热）
    if pd.notna(rsi) and 5 < rsi < 75: score += 10
    if pd.notna(close) and pd.notna(ma50) and ma50 > 0 and (close / ma50) < 1.2: score += 10

    # 波动 / 情绪 20%（中性区更佳）
    if pd.notna(close) and pd.notna(ma20) and ma20 > 0:
        ratio_20 = close / ma20
        if 0.9 < ratio_20 < 1.1: score += 10
    if pd.notna(vol_ratio) and vol_ratio < 3: score += 10

    rsi_out = (None if pd.isna(rsi) else round(rsi, 1))
    volr_out = (None if pd.isna(vol_ratio) else round(vol_ratio, 2))
    return round(score, 1), rsi_out, volr_out


def score_short(df):
    """空头评分：与多头相反的方向信号 + 中性约束，总分100"""
    close = last_val(df["Close"])
    prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else np.nan
    ma20 = last_val(df["MA20"])
    ma50 = last_val(df["MA50"])
    rsi = last_val(df["RSI"])
    macd = last_val(df["MACD"])
    signal = last_val(df["Signal"])
    vol = last_val(df["Volume"])
    vol_ma20 = last_val(df["Volume"].rolling(20).mean())
    obv = last_val(df["OBV"])
    obv_prev = float(df["OBV"].iloc[-2]) if len(df) >= 2 and pd.notna(df["OBV"].iloc[-2]) else np.nan
    obv_ma20 = last_val(df["OBV_MA20"])

    score = 0

    # 趋势动能 40%（反向）
    if pd.notna(close) and pd.notna(ma20) and close < ma20: score += 10
    if pd.notna(close) and pd.notna(ma50) and close < ma50: score += 10
    if pd.notna(rsi) and rsi <= 45: score += 10
    if pd.notna(macd) and pd.notna(signal) and macd < signal: score += 10

    # 资金流 20%
    vol_ratio = np.nan
    # 1) 放量下跌
    if pd.notna(vol) and pd.notna(vol_ma20) and vol_ma20 > 0:
        vol_ratio = vol / vol_ma20
        if pd.notna(prev_close) and pd.notna(close) and close < prev_close and vol_ratio > 1.2:
            score += 10
    # 2) OBV 下降 且 低于均线
    if pd.notna(obv) and pd.notna(obv_prev) and pd.notna(obv_ma20):
        if obv < obv_prev and obv < obv_ma20:
            score += 10

    # 估值与质量 20%（避免过度超卖）
    if pd.notna(rsi) and 5 < rsi < 75: score += 10
    if pd.notna(close) and pd.notna(ma50) and ma50 > 0 and (close / ma50) > 0.8:  # 不要过分偏离，留有下跌空间
        score += 10

    # 波动 / 情绪 20%（中性区更稳定）
    if pd.notna(close) and pd.notna(ma20) and ma20 > 0:
        ratio_20 = close / ma20
        if 0.9 < ratio_20 < 1.1: score += 10
    if pd.notna(vol_ratio) and vol_ratio < 3: score += 10

    rsi_out = (None if pd.isna(rsi) else round(rsi, 1))
    volr_out = (None if pd.isna(vol_ratio) else round(vol_ratio, 2))
    return round(score, 1), rsi_out, volr_out


# ============ ETF 概览 ============
def build_etf_overview(df, symbol):
    """为ETF生成一个不基于评分门槛的概览快照"""
    def last(s):
        v = s.iloc[-1]
        if isinstance(v, (pd.Series, np.ndarray, list)):
            v = np.asarray(v).reshape(-1)[-1]
        return float(v)

    close = last(df["Close"])
    ma20 = last(df["MA20"])
    ma50 = last(df["MA50"])
    rsi = last(df["RSI"])
    macd = last(df["MACD"])
    signal = last(df["Signal"])

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
        "与MA20偏离%": (round((close/ma20 - 1)*100, 2) if pd.notna(close) and pd.notna(ma20) and ma20 > 0 else None),
        "与MA50偏离%": (round((close/ma50 - 1)*100, 2) if pd.notna(close) and pd.notna(ma50) and ma50 > 0 else None),
    }

    # === OBV 概览 ===
    obv = last(df["OBV"])
    obv_prev = float(df["OBV"].iloc[-2]) if pd.notna(df["OBV"].iloc[-2]) else np.nan
    obv_ma20 = last(df["OBV_MA20"])

    snapshot.update({
        "OBV>MA20": (pd.notna(obv) and pd.notna(obv_ma20) and obv > obv_ma20),
        "OBV上升": (pd.notna(obv) and pd.notna(obv_prev) and obv > obv_prev),
        "与OBV_MA20偏离%": (round((obv/obv_ma20 - 1)*100, 2) if pd.notna(obv) and pd.notna(obv_ma20) and obv_ma20 != 0 else None),
    })

    return snapshot


# ============ 主逻辑 ============
results = []            # 多空都放在一起，这里记录“方向”字段
etf_overview_rows = []  # ETF 总览永远输出

for s in symbols_all:
    try:
        df = get_stock_data(s)
        if df is None:
            print(f"{s} 数据不足，跳过")
            continue

        # ETF 概览
        if s in etf_symbols:
            try:
                etf_overview_rows.append(build_etf_overview(df, s))
            except Exception as e_snap:
                print(f"{s} ETF概览生成失败: {e_snap}")

        # 多头 / 空头评分
        long_score, long_rsi, long_volr = score_long(df)
        short_score, short_rsi, short_volr = score_short(df)

        close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])
        change = (close / prev_close - 1.0) * 100.0

        # 只要达到任一方向门槛就入表；若多空都≥70，优先选择分数更高的一侧
        direction = None
        rating = None
        score = None
        rsi = None
        vol_ratio_out = None

        if long_score >= 70 or short_score >= 70:
            if long_score >= short_score:
                direction = "Long"
                score = long_score
                rsi = long_rsi
                vol_ratio_out = long_volr
                rating = "⭐ 强买入" if long_score >= 85 else "✅ 买入"
            else:
                direction = "Short"
                score = short_score
                rsi = short_rsi
                vol_ratio_out = short_volr
                rating = "🔻 强烈做空" if short_score >= 85 else "⚠️ 做空"

            results.append({
                "类别": ("ETF" if s in etf_symbols else "股票"),
                "方向": direction,
                "代码": s,
                "收盘价": round(close, 2),
                "涨跌幅 %": round(change, 2),
                "RSI": rsi,
                "成交量/均量比": vol_ratio_out,
                "策略评分": score,
                "评级": rating
            })

    except Exception as e:
        print(f"{s} 错误: {e}")

# ============ 输出整备 ============
df_result = pd.DataFrame(results)
df_etf_overview = pd.DataFrame(etf_overview_rows)

# 空模板
cols_all = ["类别","方向","代码","收盘价","涨跌幅 %","RSI","成交量/均量比","策略评分","评级"]
empty_df = pd.DataFrame(columns=cols_all)

if df_result.empty:
    print("暂无满足条件（≥70分）的标的，将导出空模板。")
    df_sorted = empty_df.copy()
else:
    df_sorted = df_result.sort_values(by=["类别", "方向", "策略评分", "代码"],
                                      ascending=[True, True, False, True])

# 分类拆分：股票 vs ETF
stock_df = df_sorted[df_sorted["类别"] == "股票"] if not df_sorted.empty else empty_df.copy()
etf_df   = df_sorted[df_sorted["类别"] == "ETF"] if not df_sorted.empty else empty_df.copy()

# 方向拆分：Long vs Short
def split_long_short(sub_df):
    long_part = sub_df[sub_df["方向"] == "Long"]
    short_part = sub_df[sub_df["方向"] == "Short"]
    return long_part, short_part

stock_long, stock_short = split_long_short(stock_df)
etf_long, etf_short = split_long_short(etf_df)

# 评级拆分：Strong / Normal
def split_rating(sub_df):
    strong_buy = sub_df[(sub_df["方向"] == "Long") & (sub_df["策略评分"] >= 85)]
    buy = sub_df[(sub_df["方向"] == "Long") & (sub_df["策略评分"] >= 70) & (sub_df["策略评分"] < 85)]
    strong_short = sub_df[(sub_df["方向"] == "Short") & (sub_df["策略评分"] >= 85)]
    short = sub_df[(sub_df["方向"] == "Short") & (sub_df["策略评分"] >= 70) & (sub_df["策略评分"] < 85)]
    return strong_buy, buy, strong_short, short

stock_strong_buy, stock_buy, stock_strong_short, stock_short_norm = split_rating(stock_df)
etf_strong_buy, etf_buy, etf_strong_short, etf_short_norm = split_rating(etf_df)

# 汇总
if df_sorted.empty:
    industry_summary = pd.DataFrame(columns=["评级","count","mean"])
else:
    industry_summary = df_sorted.groupby("评级")["策略评分"].agg(["count", "mean"]).reset_index()

# ETF Overview：布尔列转为 boolean 以便 Excel 友好展示
if not df_etf_overview.empty:
    bool_cols = ["MACD>Signal","站上MA50","站上MA20","MA50上升","MA20上升","OBV>MA20","OBV上升"]
    for c in bool_cols:
        if c in df_etf_overview.columns:
            df_etf_overview[c] = df_etf_overview[c].astype("boolean")

# ============ 导出 Excel ============
with pd.ExcelWriter(OUTPUT_PATH) as writer:
    # 股票（多头 & 空头）
    stock_strong_buy.to_excel(writer, sheet_name="Stock ⭐Strong Buy", index=False)
    stock_buy.to_excel(writer, sheet_name="Stock ✅Buy", index=False)
    stock_strong_short.to_excel(writer, sheet_name="Stock 🔻Strong Short", index=False)
    stock_short_norm.to_excel(writer, sheet_name="Stock ⚠️Short", index=False)

    # ETF（多头 & 空头）
    etf_strong_buy.to_excel(writer, sheet_name="ETF ⭐Strong Buy", index=False)
    etf_buy.to_excel(writer, sheet_name="ETF ✅Buy", index=False)
    etf_strong_short.to_excel(writer, sheet_name="ETF 🔻Strong Short", index=False)
    etf_short_norm.to_excel(writer, sheet_name="ETF ⚠️Short", index=False)

    # 概览
    industry_summary.to_excel(writer, sheet_name="Industry Summary", index=False)

    # ETF 总览（永远输出）
    if not df_etf_overview.empty:
        df_etf_overview.to_excel(writer, sheet_name="ETF Overview", index=False)
    else:
        pd.DataFrame(columns=[
            "ETF","收盘价","RSI","站上MA20","站上MA50","MACD>Signal",
            "MA20上升","MA50上升","与MA20偏离%","与MA50偏离%",
            "OBV>MA20","OBV上升","与OBV_MA20偏离%"
        ]).to_excel(writer, sheet_name="ETF Overview", index=False)

print(f"✅ 扫描完成，文件已生成：{OUTPUT_PATH}")
