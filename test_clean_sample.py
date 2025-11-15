#!/usr/bin/env python3
"""
测试清理脚本 - 小样本测试
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import time

def test_symbol_data_quality(symbol, max_retries=2):
    """测试单个股票符号的数据质量"""
    for attempt in range(max_retries):
        try:
            # 测试基本价格数据
            data = yf.download(symbol, period="3mo", interval="1d", 
                             progress=False, auto_adjust=False)
            
            if data is None or len(data) < 50:
                return False, "数据不足"
            
            # 检查基本数据完整性
            close_na_ratio = data['Close'].isna().sum() / len(data)
            if close_na_ratio > 0.1:  # 超过10%的数据缺失
                return False, "价格数据缺失过多"
            
            volume_na_ratio = data['Volume'].isna().sum() / len(data)
            if volume_na_ratio > 0.2:  # 超过20%的成交量缺失
                return False, "成交量数据缺失过多"
            
            # 测试基本面数据（仅对股票）
            try:
                stock = yf.Ticker(symbol)
                info = stock.info
                
                # 检查是否有基本的公司信息
                if not info or len(info) < 5:
                    return False, "基本面数据不可用"
                
                # 检查关键基本面指标
                key_metrics = ['marketCap', 'trailingPE', 'forwardPE', 'priceToBook', 
                             'profitMargins', 'returnOnEquity']
                available_metrics = sum(1 for metric in key_metrics if info.get(metric) is not None)
                
                if available_metrics < 2:  # 至少要有2个关键指标
                    return False, "关键基本面指标缺失"
                    
            except Exception:
                return False, "基本面数据获取失败"
            
            return True, "数据质量良好"
            
        except Exception as e:
            if attempt == max_retries - 1:
                return False, f"数据获取失败: {str(e)}"
            time.sleep(0.5)
    
    return False, "重试后仍失败"

def main():
    # 测试一些已知的好股票和坏股票
    test_symbols = [
        "AAPL",    # 应该是好的
        "MSFT",    # 应该是好的
        "GOOGL",   # 应该是好的
        "TWTR",    # 已退市，应该是坏的
        "UNITY",   # 可能有问题
        "SPY",     # ETF，应该是好的
    ]
    
    print("🧪 测试股票符号数据质量...")
    
    for symbol in test_symbols:
        print(f"\n测试 {symbol}...")
        is_valid, reason = test_symbol_data_quality(symbol)
        status = "✅" if is_valid else "❌"
        print(f"{status} {symbol}: {reason}")

if __name__ == "__main__":
    main()