#!/usr/bin/env python3
"""
Test data fetching to debug the VCP detector issue
"""

import yfinance as yf
import pandas as pd
import numpy as np

def test_data_fetch(symbol):
    """Test basic data fetching"""
    print(f"\n🔍 Testing data fetch for {symbol}")
    print("=" * 40)
    
    try:
        # Basic fetch
        print("1. Basic data fetch...")
        data = yf.download(symbol, period="1y", interval="1d", progress=False, auto_adjust=False)
        print(f"   Raw data shape: {data.shape}")
        print(f"   Columns: {list(data.columns)}")
        
        if len(data) == 0:
            print("   ❌ No data returned")
            return
        
        # Handle multi-level columns
        if isinstance(data.columns, pd.MultiIndex):
            print("   📊 Multi-level columns detected, flattening...")
            data.columns = data.columns.get_level_values(0)
        
        print(f"   ✅ Data loaded: {len(data)} rows")
        print(f"   📈 Price range: ${data['Close'].min():.2f} - ${data['Close'].max():.2f}")
        print(f"   📅 Date range: {data.index[0].date()} to {data.index[-1].date()}")
        
        # Test technical indicators
        print("\n2. Testing technical indicators...")
        data['MA20'] = data['Close'].rolling(window=20).mean()
        data['MA50'] = data['Close'].rolling(window=50).mean()
        data['MA150'] = data['Close'].rolling(window=150).mean()
        
        print(f"   MA20 valid values: {data['MA20'].notna().sum()}")
        print(f"   MA50 valid values: {data['MA50'].notna().sum()}")
        print(f"   MA150 valid values: {data['MA150'].notna().sum()}")
        
        # Check after dropna
        print("\n3. After dropna()...")
        clean_data = data.dropna()
        print(f"   Clean data shape: {clean_data.shape}")
        
        if len(clean_data) > 0:
            print(f"   ✅ Clean data available: {len(clean_data)} rows")
            print(f"   📈 Latest close: ${clean_data['Close'].iloc[-1]:.2f}")
        else:
            print("   ❌ No data after dropna()")
            print("   🔍 Checking NaN values...")
            for col in data.columns:
                nan_count = data[col].isna().sum()
                if nan_count > 0:
                    print(f"      {col}: {nan_count} NaN values")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

# Test with a few symbols
test_symbols = ["AAPL", "MSFT", "SPY"]

print("🎯 Data Fetch Debug Test")
print("=" * 50)

for symbol in test_symbols:
    test_data_fetch(symbol)