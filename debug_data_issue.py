#!/usr/bin/env python3
"""
调试数据问题
"""

import yfinance as yf
import pandas as pd

def debug_symbol(symbol):
    print(f"\n🔍 调试 {symbol}...")
    
    try:
        # 步骤1: 下载数据
        print("步骤1: 下载价格数据...")
        data = yf.download(symbol, period="3mo", interval="1d", 
                         progress=False, auto_adjust=False)
        print(f"数据形状: {data.shape}")
        print(f"数据类型: {type(data)}")
        print(f"列名: {list(data.columns)}")
        
        # 步骤2: 检查数据长度
        print("步骤2: 检查数据长度...")
        if data is None:
            print("❌ 数据为None")
            return
        if len(data) < 50:
            print(f"❌ 数据不足: {len(data)} < 50")
            return
        print(f"✅ 数据长度充足: {len(data)}")
        
        # 步骤3: 检查缺失值
        print("步骤3: 检查缺失值...")
        close_na_count = data['Close'].isna().sum()
        close_na_ratio = close_na_count / len(data)
        print(f"Close缺失值: {close_na_count}/{len(data)} = {close_na_ratio:.2%}")
        
        volume_na_count = data['Volume'].isna().sum()
        volume_na_ratio = volume_na_count / len(data)
        print(f"Volume缺失值: {volume_na_count}/{len(data)} = {volume_na_ratio:.2%}")
        
        # 步骤4: 检查基本面数据
        print("步骤4: 检查基本面数据...")
        stock = yf.Ticker(symbol)
        info = stock.info
        print(f"Info字典长度: {len(info) if info else 0}")
        
        if info and len(info) >= 5:
            key_metrics = ['marketCap', 'trailingPE', 'forwardPE', 'priceToBook', 
                         'profitMargins', 'returnOnEquity']
            available_metrics = []
            for metric in key_metrics:
                value = info.get(metric)
                if value is not None:
                    available_metrics.append(metric)
                    print(f"  ✅ {metric}: {value}")
                else:
                    print(f"  ❌ {metric}: None")
            
            print(f"可用关键指标: {len(available_metrics)}/6")
            
            if len(available_metrics) >= 2:
                print("✅ 基本面数据充足")
            else:
                print("❌ 基本面数据不足")
        else:
            print("❌ 基本面数据不可用")
        
        print(f"✅ {symbol} 数据质量检查完成")
        
    except Exception as e:
        print(f"❌ {symbol} 错误: {e}")
        import traceback
        traceback.print_exc()

def main():
    test_symbols = ["AAPL", "TWTR", "SPY"]
    
    for symbol in test_symbols:
        debug_symbol(symbol)

if __name__ == "__main__":
    main()