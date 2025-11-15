
#!/usr/bin/env python3
"""
美国股票和ETF扫描程序 - 增强版本 + 基本面分析
Enhanced US Stock and ETF Scanner with Technical Analysis, Quality Filters, Multi-Timeframe Confirmation, and Fundamental Analysis

功能特点:
- 扫描1256个股票 + 50个ETF
- 技术指标分析 (RSI, MACD, 移动平均线)
- 增强质量过滤器 (6个额外标准, 30分)
- 多时间框架确认 (周线趋势分析, 10分)
- 基本面分析 (估值、盈利能力、成长性、财务健康度, 50分)
- 历史跟踪和新强买入检测
- 批量处理优化 (50个符号/批次)
- 结构化文件夹输出 (按日期组织)
- 总评分系统: 190分 (原100分 + 30质量分 + 10周线分 + 50基本面分)
- 阈值: 强买入≥120分, 买入≥100分
"""

import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timedelta
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# 导入股票符号
from stock_symbols_2000 import STOCK_SYMBOLS, ETF_SYMBOLS

# ============ 参数设置 ============
symbols = STOCK_SYMBOLS  # 1256 US stocks
etf_symbols = ETF_SYMBOLS  # 50 ETFs

# 合并为总扫描列表（不重复）
symbols_all = list(dict.fromkeys(symbols + etf_symbols))

# 评分阈值 (基于190分总分) - 高门槛精选
STRONG_BUY_THRESHOLD = 150  # 强买入阈值 (精选约10个股票)
BUY_THRESHOLD = 120         # 买入阈值 (提高到120分)

# 创建结果文件夹结构
RESULTS_BASE_DIR = "results"
DATE_FOLDER = datetime.now().strftime('%Y%m%d')
RESULTS_DIR = os.path.join(RESULTS_BASE_DIR, DATE_FOLDER)

# 确保文件夹存在
os.makedirs(RESULTS_DIR, exist_ok=True)

OUTPUT_PATH = os.path.join(RESULTS_DIR, f"US_StrongBuy_Scan_{DATE_FOLDER}.xlsx")
HISTORY_FILE = "scan_history.json"  # 保持在根目录

def get_fundamental_score(symbol, max_retries=2):
    """
    获取基本面分析评分 (最多50分)
    分析估值、盈利能力、成长性、财务健康度和股息质量
    """
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            if not info or len(info) < 10:
                return 0, {}
            
            score = 0
            details = {}
            
            # 1. 估值指标 (0-12分)
            valuation_score = 0
            
            # P/E比率评分 (0-4分)
            pe_ratio = info.get('trailingPE') or info.get('forwardPE')
            if pe_ratio and pe_ratio > 0:
                details['PE_Ratio'] = pe_ratio
                if pe_ratio < 15:  # 低估值
                    valuation_score += 4
                elif pe_ratio < 20:  # 合理估值
                    valuation_score += 3
                elif pe_ratio < 25:  # 略高估值
                    valuation_score += 2
                elif pe_ratio < 35:  # 高估值但可接受
                    valuation_score += 1
            
            # P/B比率评分 (0-4分)
            pb_ratio = info.get('priceToBook')
            if pb_ratio and pb_ratio > 0:
                details['PB_Ratio'] = pb_ratio
                if pb_ratio < 1.5:  # 低估值
                    valuation_score += 4
                elif pb_ratio < 2.5:  # 合理估值
                    valuation_score += 3
                elif pb_ratio < 4:  # 略高估值
                    valuation_score += 2
                elif pb_ratio < 6:  # 高估值但可接受
                    valuation_score += 1
            
            # P/S比率评分 (0-4分)
            ps_ratio = info.get('priceToSalesTrailing12Months')
            if ps_ratio and ps_ratio > 0:
                details['PS_Ratio'] = ps_ratio
                if ps_ratio < 2:  # 低估值
                    valuation_score += 4
                elif ps_ratio < 4:  # 合理估值
                    valuation_score += 3
                elif ps_ratio < 6:  # 略高估值
                    valuation_score += 2
                elif ps_ratio < 10:  # 高估值但可接受
                    valuation_score += 1
            
            score += valuation_score
            details['Valuation_Score'] = valuation_score
            
            # 2. 盈利能力指标 (0-12分)
            profitability_score = 0
            
            # 净利润率 (0-4分)
            profit_margin = info.get('profitMargins')
            if profit_margin and profit_margin > 0:
                details['Profit_Margin'] = profit_margin * 100
                if profit_margin > 0.20:  # >20%
                    profitability_score += 4
                elif profit_margin > 0.15:  # >15%
                    profitability_score += 3
                elif profit_margin > 0.10:  # >10%
                    profitability_score += 2
                elif profit_margin > 0.05:  # >5%
                    profitability_score += 1
            
            # ROE (0-4分)
            roe = info.get('returnOnEquity')
            if roe and roe > 0:
                details['ROE'] = roe * 100
                if roe > 0.20:  # >20%
                    profitability_score += 4
                elif roe > 0.15:  # >15%
                    profitability_score += 3
                elif roe > 0.10:  # >10%
                    profitability_score += 2
                elif roe > 0.05:  # >5%
                    profitability_score += 1
            
            # ROA (0-4分)
            roa = info.get('returnOnAssets')
            if roa and roa > 0:
                details['ROA'] = roa * 100
                if roa > 0.10:  # >10%
                    profitability_score += 4
                elif roa > 0.07:  # >7%
                    profitability_score += 3
                elif roa > 0.05:  # >5%
                    profitability_score += 2
                elif roa > 0.02:  # >2%
                    profitability_score += 1
            
            score += profitability_score
            details['Profitability_Score'] = profitability_score
            
            # 3. 成长性指标 (0-12分)
            growth_score = 0
            
            # 营收增长 (0-6分)
            revenue_growth = info.get('revenueGrowth')
            if revenue_growth is not None:
                details['Revenue_Growth'] = revenue_growth * 100
                if revenue_growth > 0.20:  # >20%
                    growth_score += 6
                elif revenue_growth > 0.15:  # >15%
                    growth_score += 5
                elif revenue_growth > 0.10:  # >10%
                    growth_score += 4
                elif revenue_growth > 0.05:  # >5%
                    growth_score += 3
                elif revenue_growth > 0:  # 正增长
                    growth_score += 2
                elif revenue_growth > -0.05:  # 轻微下降
                    growth_score += 1
            
            # 盈利增长 (0-6分)
            earnings_growth = info.get('earningsGrowth')
            if earnings_growth is not None:
                details['Earnings_Growth'] = earnings_growth * 100
                if earnings_growth > 0.25:  # >25%
                    growth_score += 6
                elif earnings_growth > 0.15:  # >15%
                    growth_score += 5
                elif earnings_growth > 0.10:  # >10%
                    growth_score += 4
                elif earnings_growth > 0.05:  # >5%
                    growth_score += 3
                elif earnings_growth > 0:  # 正增长
                    growth_score += 2
                elif earnings_growth > -0.10:  # 轻微下降
                    growth_score += 1
            
            score += growth_score
            details['Growth_Score'] = growth_score
            
            # 4. 财务健康度 (0-10分)
            financial_health_score = 0
            
            # 流动比率 (0-3分)
            current_ratio = info.get('currentRatio')
            if current_ratio and current_ratio > 0:
                details['Current_Ratio'] = current_ratio
                if current_ratio > 2:  # 很好
                    financial_health_score += 3
                elif current_ratio > 1.5:  # 良好
                    financial_health_score += 2
                elif current_ratio > 1:  # 可接受
                    financial_health_score += 1
            
            # 债务股权比 (0-4分)
            debt_to_equity = info.get('debtToEquity')
            if debt_to_equity is not None:
                details['Debt_to_Equity'] = debt_to_equity
                if debt_to_equity < 30:  # 很低债务
                    financial_health_score += 4
                elif debt_to_equity < 50:  # 低债务
                    financial_health_score += 3
                elif debt_to_equity < 100:  # 中等债务
                    financial_health_score += 2
                elif debt_to_equity < 200:  # 高债务但可管理
                    financial_health_score += 1
            
            # 自由现金流 (0-3分)
            free_cashflow = info.get('freeCashflow')
            if free_cashflow is not None:
                details['Free_Cashflow'] = free_cashflow
                if free_cashflow > 0:
                    financial_health_score += 3
                elif free_cashflow > -1000000000:  # -10亿以内
                    financial_health_score += 1
            
            score += financial_health_score
            details['Financial_Health_Score'] = financial_health_score
            
            # 5. 股息质量 (0-4分) - 仅适用于有股息的股票
            dividend_score = 0
            dividend_yield = info.get('dividendYield')
            payout_ratio = info.get('payoutRatio')
            
            if dividend_yield and dividend_yield > 0:
                details['Dividend_Yield'] = dividend_yield * 100
                details['Payout_Ratio'] = payout_ratio * 100 if payout_ratio else None
                
                # 股息收益率评分 (0-2分)
                if 0.02 <= dividend_yield <= 0.06:  # 2-6%的健康股息
                    dividend_score += 2
                elif 0.01 <= dividend_yield <= 0.08:  # 1-8%的可接受股息
                    dividend_score += 1
                
                # 派息比率评分 (0-2分)
                if payout_ratio and 0 < payout_ratio <= 0.6:  # 健康的派息比率
                    dividend_score += 2
                elif payout_ratio and 0 < payout_ratio <= 0.8:  # 可接受的派息比率
                    dividend_score += 1
            else:
                # 对于不派息的成长股，给予中性评分
                dividend_score = 2
                details['Dividend_Yield'] = 0
                details['Payout_Ratio'] = 0
            
            score += dividend_score
            details['Dividend_Score'] = dividend_score
            
            details['Total_Fundamental_Score'] = score
            return min(score, 50), details  # 最大50分
            
        except Exception as e:
            if attempt == max_retries - 1:
                return 0, {}
            time.sleep(0.1)
    
    return 0, {}

def get_weekly_trend_score(symbol, max_retries=2):
    """
    获取周线趋势确认评分 (最多10分)
    使用3个月的周线数据进行趋势分析
    """
    for attempt in range(max_retries):
        try:
            # 获取3个月的周线数据
            weekly_data = yf.download(symbol, period="3mo", interval="1wk", progress=False)
            
            if weekly_data.empty or len(weekly_data) < 8:
                return 0
            
            weekly_data = weekly_data.dropna()
            close_prices = weekly_data['Close']
            
            # 计算周线技术指标
            weekly_rsi = ta.momentum.RSIIndicator(close_prices, window=14).rsi()
            weekly_ma20 = close_prices.rolling(window=8).mean()  # 8周约等于20日
            weekly_ma50 = close_prices.rolling(window=12).mean()  # 12周约等于50日
            
            current_price = close_prices.iloc[-1]
            current_rsi = weekly_rsi.iloc[-1]
            current_ma20 = weekly_ma20.iloc[-1]
            current_ma50 = weekly_ma50.iloc[-1]
            
            score = 0
            
            # 1. 周线RSI健康 (0-3分)
            if pd.notna(current_rsi):
                if 40 <= current_rsi <= 70:  # 健康区间
                    score += 3
                elif 30 <= current_rsi <= 80:  # 可接受区间
                    score += 2
                elif current_rsi > 20:  # 避免超卖
                    score += 1
            
            # 2. 周线均线排列 (0-4分)
            if pd.notna(current_ma20) and pd.notna(current_ma50):
                if current_price > current_ma20 > current_ma50:  # 完美排列
                    score += 4
                elif current_price > current_ma20:  # 短期趋势良好
                    score += 2
                elif current_price > current_ma50:  # 长期趋势良好
                    score += 1
            
            # 3. 周线趋势强度 (0-3分)
            if len(close_prices) >= 4:
                recent_trend = (current_price - close_prices.iloc[-4]) / close_prices.iloc[-4]
                if recent_trend > 0.05:  # 4周内上涨5%以上
                    score += 3
                elif recent_trend > 0.02:  # 4周内上涨2%以上
                    score += 2
                elif recent_trend > 0:  # 4周内上涨
                    score += 1
            
            return min(score, 10)  # 最大10分
            
        except Exception as e:
            if attempt == max_retries - 1:
                return 0
            time.sleep(0.1)
    
    return 0

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
        if recent_records[date].get('score', 0) >= STRONG_BUY_THRESHOLD:
            return False  # 最近5天内已经是强买入了
    
    return current_score >= STRONG_BUY_THRESHOLD  # 当前是强买入且最近5天不是

def categorize_stock(score, is_new):
    """根据评分和是否新出现来分类股票 (增强版阈值)"""
    if score >= STRONG_BUY_THRESHOLD:
        if is_new:
            return "🔥 新强买入"  # 最佳买入时机
        else:
            return "⭐ 强买入"    # 持续强买入
    elif score >= BUY_THRESHOLD:
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

def get_stock_data(symbol):
    """获取股票数据"""
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

def score_stock(df):
    """基础技术分析评分 (100分)"""
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

    # ============ 增强质量过滤器 (30分) ============
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

def score_stock_comprehensive(df, symbol):
    """综合评分函数，包含技术分析、质量过滤、周线确认和基本面分析"""
    # 获取技术分析评分 (130分: 100基础 + 30质量)
    technical_score, rsi_out, volr_out = score_stock(df)
    
    # 获取周线趋势确认分数 (10分)
    weekly_score = get_weekly_trend_score(symbol)
    
    # 获取基本面分析评分 (50分) - 仅对股票进行基本面分析
    fundamental_score = 0
    fundamental_details = {}
    if symbol not in etf_symbols:  # 只对股票进行基本面分析
        fundamental_score, fundamental_details = get_fundamental_score(symbol)
    
    # 合并评分 (最高190分)
    total_score = technical_score + weekly_score + fundamental_score
    
    return round(total_score, 1), rsi_out, volr_out, fundamental_details

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

# ============ 主逻辑（优化版本 + 历史跟踪 + 基本面分析）============
def main():
    print(f"📊 扫描配置:")
    print(f"   - 股票数量: {len(symbols)}")
    print(f"   - ETF数量: {len(etf_symbols)}")
    print(f"   - 总扫描数量: {len(symbols_all)}")
    print(f"   - 预计扫描时间: {len(symbols_all) * 3 // 60}分钟 (估算，包含基本面分析)")
    print(f"   - 强买入阈值: {STRONG_BUY_THRESHOLD}分 (精选约10个股票)")
    print(f"   - 买入阈值: {BUY_THRESHOLD}分")
    print("=" * 50)

    results = []
    etf_overview_rows = []
    processed_count = 0
    error_count = 0
    qualified_count = 0
    new_strong_buy_count = 0

    # 加载历史记录
    print("📚 加载历史扫描记录...")
    scan_history = load_scan_history()

    print("🚀 开始扫描（技术分析 + 基本面分析）...")
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

                    # 综合评分 (技术分析 + 周线确认 + 基本面分析)
                    score, rsi_val, vol_ratio, fundamental_details = score_stock_comprehensive(df, symbol)
                    close_val = float(df["Close"].iloc[-1])
                    prev_close = float(df["Close"].iloc[-2])
                    change = (close_val / prev_close - 1.0) * 100.0
                    
                    # 检查是否为新强买入
                    is_new = is_new_strong_buy(scan_history, symbol, score)
                    category = categorize_stock(score, is_new)
                    
                    # 更新历史记录
                    if score >= BUY_THRESHOLD:  # 只记录合格的股票
                        update_stock_history(scan_history, symbol, score, category)
                    
                    if score >= BUY_THRESHOLD:  # 合格分数线
                        qualified_count += 1
                        if category == "🔥 新强买入":
                            new_strong_buy_count += 1
                        
                        # 构建结果记录
                        result_record = {
                            "类别": ("ETF" if symbol in etf_symbols else "股票"),
                            "代码": symbol,
                            "收盘价": round(close_val, 2),
                            "涨跌幅 %": round(change, 2),
                            "RSI": rsi_val,
                            "成交量/均量比": vol_ratio,
                            "策略评分": score,
                            "评级": category,
                            "是否新出现": "是" if is_new and score >= STRONG_BUY_THRESHOLD else "否"
                        }
                        
                        # 添加基本面分析详情（仅对股票）
                        if symbol not in etf_symbols and fundamental_details:
                            result_record.update({
                                "基本面评分": fundamental_details.get('Total_Fundamental_Score', 0),
                                "估值评分": fundamental_details.get('Valuation_Score', 0),
                                "盈利能力评分": fundamental_details.get('Profitability_Score', 0),
                                "成长性评分": fundamental_details.get('Growth_Score', 0),
                                "财务健康评分": fundamental_details.get('Financial_Health_Score', 0),
                                "股息评分": fundamental_details.get('Dividend_Score', 0),
                                "PE比率": fundamental_details.get('PE_Ratio'),
                                "PB比率": fundamental_details.get('PB_Ratio'),
                                "PS比率": fundamental_details.get('PS_Ratio'),
                                "净利润率%": fundamental_details.get('Profit_Margin'),
                                "ROE%": fundamental_details.get('ROE'),
                                "ROA%": fundamental_details.get('ROA'),
                                "营收增长%": fundamental_details.get('Revenue_Growth'),
                                "盈利增长%": fundamental_details.get('Earnings_Growth'),
                                "流动比率": fundamental_details.get('Current_Ratio'),
                                "债务股权比": fundamental_details.get('Debt_to_Equity'),
                                "股息收益率%": fundamental_details.get('Dividend_Yield'),
                                "派息比率%": fundamental_details.get('Payout_Ratio')
                            })
                        
                        results.append(result_record)
                        
                        # 实时显示高分股票（优先显示新强买入）
                        if category == "🔥 新强买入":
                            print(f"🔥 发现新强买入: {symbol} (评分: {score}) - 最佳买入时机!")
                        elif score >= STRONG_BUY_THRESHOLD:
                            print(f"⭐ 发现强买入: {symbol} (评分: {score})")
                        elif score >= 130:  # 调整显示阈值
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
    print(f"   - ⭐ 强买入(≥{STRONG_BUY_THRESHOLD}分): {len([r for r in results if r['策略评分'] >= STRONG_BUY_THRESHOLD and r['评级'] != '🔥 新强买入'])}")
    print(f"   - ✅ 买入({BUY_THRESHOLD}-{STRONG_BUY_THRESHOLD-1}分): {len([r for r in results if BUY_THRESHOLD <= r['策略评分'] < STRONG_BUY_THRESHOLD])}")
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
        print(f"暂无满足条件（评分≥{BUY_THRESHOLD}）的标的，将导出空模板。")
        df_result_sorted = empty_pick_df.copy()
    else:
        df_result_sorted = df_result.sort_values(by="策略评分", ascending=False)

    # 按类别拆分
    stock_df = df_result_sorted[df_result_sorted["类别"] == "股票"]
    etf_df   = df_result_sorted[df_result_sorted["类别"] == "ETF"]

    # 各自拆分新强买入/强买入/买入
    def split_tables(sub_df):
        new_strong_buy = sub_df[sub_df["评级"] == "🔥 新强买入"]
        strong_buy = sub_df[(sub_df["策略评分"] >= STRONG_BUY_THRESHOLD) & (sub_df["评级"] != "🔥 新强买入")]
        buy = sub_df[(sub_df["策略评分"] >= BUY_THRESHOLD) & (sub_df["策略评分"] < STRONG_BUY_THRESHOLD)]
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
    base_name = f"US_StrongBuy_Scan_{DATE_FOLDER}"

    # 保存各个分类为单独的CSV文件到日期文件夹
    # 🔥 新强买入 (最佳买入时机)
    stock_new_strong.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_Stock_NewStrongBuy.csv"), index=False)
    etf_new_strong.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_ETF_NewStrongBuy.csv"), index=False)

    # ⭐ 强买入 (持续强买入)
    stock_strong.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_Stock_StrongBuy.csv"), index=False)
    etf_strong.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_ETF_StrongBuy.csv"), index=False)

    # ✅ 买入
    stock_buy.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_Stock_Buy.csv"), index=False)
    etf_buy.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_ETF_Buy.csv"), index=False)

    # 汇总统计
    industry_summary.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_Category_Summary.csv"), index=False)

    # ETF总览CSV
    if not df_etf_overview.empty:
        df_etf_overview.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_ETF_Overview.csv"), index=False)
    else:
        pd.DataFrame(columns=["ETF","收盘价","RSI","站上MA20","站上MA50","MACD>Signal","MA20上升","MA50上升","与MA20偏离%","与MA50偏离%"])\
          .to_csv(os.path.join(RESULTS_DIR, f"{base_name}_ETF_Overview.csv"), index=False)

    # 创建一个汇总的所有结果文件
    if not df_result_sorted.empty:
        df_result_sorted.to_csv(os.path.join(RESULTS_DIR, f"{base_name}_All_Results.csv"), index=False)

    print(f"✅ 扫描完成，文件已生成：")
    print(f"📁 结果文件夹: {RESULTS_DIR}")
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
    print(f"\n📁 所有文件已保存到: {RESULTS_DIR}")

    # 显示最佳投资机会（优先显示新强买入）
    if not df_result_sorted.empty:
        print(f"\n🏆 前10个最佳投资机会:")
        print("=" * 90)
        for i, (_, row) in enumerate(df_result_sorted.head(10).iterrows()):
            rating_emoji = "🔥" if row['评级'] == '🔥 新强买入' else ("⭐" if row['策略评分'] >= STRONG_BUY_THRESHOLD else "✅")
            print(f"{rating_emoji} {row['代码']:>6} | {row['类别']:>3} | {row['策略评分']:>5.1f}分 | ${row['收盘价']:>8.2f} | {row['涨跌幅 %']:>6.1f}%")

if __name__ == "__main__":
    main()