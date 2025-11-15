import yfinance as yf
import pandas as pd

def explore_fundamental_data():
    """Explore what fundamental data is available from Yahoo Finance"""
    
    # Test with a well-known stock
    symbol = "AAPL"
    stock = yf.Ticker(symbol)
    
    print(f"🔍 Exploring fundamental data for {symbol}...")
    print("=" * 60)
    
    try:
        # Get basic info
        info = stock.info
        print("📊 Basic Info Keys:")
        for key in sorted(info.keys()):
            print(f"  - {key}: {info.get(key)}")
        print()
        
        # Financial statements
        print("📈 Financial Statements Available:")
        
        # Income Statement
        try:
            income_stmt = stock.financials
            print(f"  ✅ Income Statement: {income_stmt.shape if income_stmt is not None else 'None'}")
            if income_stmt is not None and not income_stmt.empty:
                print(f"     Columns: {list(income_stmt.index)[:10]}...")  # Show first 10
        except Exception as e:
            print(f"  ❌ Income Statement: {e}")
        
        # Balance Sheet
        try:
            balance_sheet = stock.balance_sheet
            print(f"  ✅ Balance Sheet: {balance_sheet.shape if balance_sheet is not None else 'None'}")
            if balance_sheet is not None and not balance_sheet.empty:
                print(f"     Columns: {list(balance_sheet.index)[:10]}...")  # Show first 10
        except Exception as e:
            print(f"  ❌ Balance Sheet: {e}")
        
        # Cash Flow
        try:
            cash_flow = stock.cashflow
            print(f"  ✅ Cash Flow: {cash_flow.shape if cash_flow is not None else 'None'}")
            if cash_flow is not None and not cash_flow.empty:
                print(f"     Columns: {list(cash_flow.index)[:10]}...")  # Show first 10
        except Exception as e:
            print(f"  ❌ Cash Flow: {e}")
        
        print()
        
        # Key fundamental metrics from info
        print("💰 Key Fundamental Metrics from Info:")
        fundamental_keys = [
            'marketCap', 'enterpriseValue', 'trailingPE', 'forwardPE', 
            'pegRatio', 'priceToBook', 'priceToSalesTrailing12Months',
            'enterpriseToRevenue', 'enterpriseToEbitda', 'profitMargins',
            'operatingMargins', 'returnOnAssets', 'returnOnEquity',
            'revenueGrowth', 'earningsGrowth', 'currentRatio', 'quickRatio',
            'debtToEquity', 'totalCash', 'totalDebt', 'freeCashflow',
            'operatingCashflow', 'earningsQuarterlyGrowth', 'revenueQuarterlyGrowth',
            'grossMargins', 'ebitdaMargins', 'bookValue', 'priceToBook',
            'beta', 'dividendYield', 'payoutRatio', 'trailingAnnualDividendYield'
        ]
        
        available_metrics = {}
        for key in fundamental_keys:
            value = info.get(key)
            if value is not None:
                available_metrics[key] = value
                print(f"  ✅ {key}: {value}")
            else:
                print(f"  ❌ {key}: Not available")
        
        print()
        print(f"📊 Total available fundamental metrics: {len(available_metrics)}")
        
        return available_metrics
        
    except Exception as e:
        print(f"❌ Error exploring fundamental data: {e}")
        return {}

if __name__ == "__main__":
    explore_fundamental_data()