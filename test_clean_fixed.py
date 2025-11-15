#!/usr/bin/env python3
"""
测试修复版清理脚本 - 小样本
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import time
from stock_symbols_2000 import STOCK_SYMBOLS, ETF_SYMBOLS

def test_symbol_data_quality(symbol, max_retries=2):
    """测试单个股票符号的数据质量"""
    for attempt in range(max_retries):
        try:
            # 测试基本价格数据
            data = yf.download(symbol, period="3mo", interval="1d", 
                             progress=False, auto_adjust=False)
            
            if data is None or len(data) < 50:
                return False, "数据不足"
            
            # 处理多级列名问题
            if isinstance(data.columns, pd.MultiIndex):
                # 如果是多级列名，取第一级
                data.columns = data.columns.get_level_values(0)
            
            # 检查基本数据完整性
            close_na_count = data['Close'].isna().sum()
            close_na_ratio = close_na_count / len(data)
            if close_na_ratio > 0.1:  # 超过10%的数据缺失
                return False, "价格数据缺失过多"
            
            volume_na_count = data['Volume'].isna().sum()
            volume_na_ratio = volume_na_count / len(data)
            if volume_na_ratio > 0.2:  # 超过20%的成交量缺失
                return False, "成交量数据缺失过多"
            
            # 测试基本面数据（仅对股票）
            if symbol not in ETF_SYMBOLS:
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
    print("🧪 测试修复版清理脚本 (前50个股票)...")
    
    # 测试前50个股票
    test_stocks = STOCK_SYMBOLS[:50]
    test_etfs = ETF_SYMBOLS[:10]  # 测试前10个ETF
    
    print(f"测试股票: {len(test_stocks)} 个")
    print(f"测试ETF: {len(test_etfs)} 个")
    
    valid_stocks = []
    invalid_stocks = []
    
    print("\n🔍 测试股票...")
    for i, symbol in enumerate(test_stocks):
        print(f"测试 {symbol} ({i+1}/{len(test_stocks)})...")
        is_valid, reason = test_symbol_data_quality(symbol)
        
        if is_valid:
            valid_stocks.append(symbol)
            print(f"✅ {symbol}: 数据质量良好")
        else:
            invalid_stocks.append((symbol, reason))
            print(f"❌ {symbol}: {reason}")
        
        time.sleep(0.1)
    
    valid_etfs = []
    invalid_etfs = []
    
    print("\n🔍 测试ETF...")
    for i, symbol in enumerate(test_etfs):
        print(f"测试 {symbol} ({i+1}/{len(test_etfs)})...")
        is_valid, reason = test_symbol_data_quality(symbol)
        
        if is_valid:
            valid_etfs.append(symbol)
            print(f"✅ {symbol}: 数据质量良好")
        else:
            invalid_etfs.append((symbol, reason))
            print(f"❌ {symbol}: {reason}")
        
        time.sleep(0.1)
    
    print(f"\n📊 测试结果:")
    print(f"   - 有效股票: {len(valid_stocks)}/{len(test_stocks)} ({len(valid_stocks)/len(test_stocks)*100:.1f}%)")
    print(f"   - 有效ETF: {len(valid_etfs)}/{len(test_etfs)} ({len(valid_etfs)/len(test_etfs)*100:.1f}%)")
    print(f"   - 总体质量: {(len(valid_stocks) + len(valid_etfs))/(len(test_stocks) + len(test_etfs))*100:.1f}%")
    
    if valid_stocks:
        print(f"\n✅ 有效股票样本: {valid_stocks[:10]}")
    if valid_etfs:
        print(f"✅ 有效ETF样本: {valid_etfs}")
    
    if invalid_stocks:
        print(f"\n❌ 无效股票样本:")
        for symbol, reason in invalid_stocks[:5]:
            print(f"   - {symbol}: {reason}")
    
    if invalid_etfs:
        print(f"\n❌ 无效ETF样本:")
        for symbol, reason in invalid_etfs:
            print(f"   - {symbol}: {reason}")

if __name__ == "__main__":
    main()