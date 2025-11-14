# US Stock & ETF Scanner

A comprehensive Python-based stock and ETF scanning system that analyzes 1000+ US stocks and 50 ETFs using technical indicators to identify strong buy and buy opportunities.

## Features

- **1000 US Stocks**: Comprehensive coverage across all major sectors
- **50 ETFs**: Major market ETFs including SPY, QQQ, IWM, and sector-specific ETFs
- **Technical Analysis**: RSI, MACD, Moving Averages (20-day, 50-day), Volume analysis
- **Scoring System**: 100-point algorithm across 4 categories (Trend, Capital Flow, Valuation, Volatility)
- **Excel Output**: Multi-sheet reports with detailed analysis and ETF overview
- **Progress Tracking**: Real-time scanning progress with ETA estimates

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies**:
   ```bash
   # Option 1: Using pip (recommended - use virtual environment)
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   
   # Option 2: Using pip with --user flag
   pip install --user -r requirements.txt
   
   # Option 3: Using conda
   conda install yfinance pandas numpy ta openpyxl
   ```

3. **Verify installation**:
   ```bash
   python3 -c "import yfinance, pandas, numpy, ta; print('All dependencies installed successfully!')"
   ```

## Usage

### Basic Usage
```bash
python3 us_stock_etf_scan.py
```

### What the Scanner Does

1. **Downloads 3 months of daily data** for 1050 symbols (1000 stocks + 50 ETFs)
2. **Calculates technical indicators** for each symbol
3. **Applies scoring algorithm** to identify strong opportunities
4. **Generates Excel report** with multiple sheets:
   - Stock ⭐Strong Buy (Score ≥ 85)
   - Stock ✅Buy (Score 70-84)
   - ETF ⭐Strong Buy (Score ≥ 85)
   - ETF ✅Buy (Score 70-84)
   - Industry Summary
   - ETF Overview (all ETFs regardless of score)

### Expected Runtime
- **Estimated time**: 15-20 minutes for full scan
- **Progress updates**: Every 50 symbols processed
- **Real-time notifications**: High-scoring stocks displayed immediately

## File Structure

```
stock_scan/
├── us_stock_etf_scan.py      # Main scanning script
├── stock_symbols.py          # 1000 stock symbols organized by sector
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── US_StrongBuy_Scan_YYYYMMDD.xlsx  # Generated output
```

## Scoring Algorithm

The system uses a 100-point scoring system across 4 categories:

### 1. Trend Momentum (40 points)
- Price above 20-day MA (10 pts)
- Price above 50-day MA (10 pts)
- RSI ≥ 55 (10 pts)
- MACD > Signal line (10 pts)

### 2. Capital Flow (20 points)
- Volume > 1.2x average (10 pts)
- Price + MACD momentum alignment (10 pts)

### 3. Valuation & Quality (20 points)
- RSI between 5-75 (not overbought/oversold) (10 pts)
- Price within 20% of 50-day MA (10 pts)

### 4. Volatility/Sentiment (20 points)
- Price within 10% of 20-day MA (10 pts)
- Volume ratio < 3x (not excessive) (10 pts)

## Stock Universe

The scanner covers **1000 stocks** across major sectors:
- **Technology**: 100 stocks (AAPL, MSFT, GOOGL, etc.)
- **Healthcare**: 100 stocks (JNJ, PFE, UNH, etc.)
- **Financial**: 100 stocks (JPM, BAC, BRK.B, etc.)
- **Consumer Discretionary**: 100 stocks (AMZN, TSLA, HD, etc.)
- **Consumer Staples**: 100 stocks (PG, KO, WMT, etc.)
- **Energy**: 100 stocks (XOM, CVX, COP, etc.)
- **Materials & Industrials**: 100 stocks (CAT, DE, HON, etc.)
- **Real Estate & REITs**: 100 stocks (AMT, PLD, O, etc.)
- **Utilities**: 60 stocks (NEE, DUK, SO, etc.)
- **Communication Services**: 80 stocks (META, DIS, NFLX, etc.)
- **Additional Stocks**: 60 stocks from various indices

Plus **50 ETFs** covering:
- Broad market (SPY, QQQ, IWM)
- Sectors (XLF, XLE, XLK, etc.)
- International (VEA, VWO)
- Bonds (AGG, BND, LQD)
- Commodities (GLD, SLV, USO)

## Output Format

The Excel file contains:
- **Timestamp**: File named with current date
- **Multiple sheets**: Organized by category and rating
- **Key metrics**: Price, change %, RSI, volume ratio, score
- **ETF Overview**: Technical snapshot of all ETFs

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError**: Install required packages using pip
2. **Slow performance**: Normal for 1000+ symbols, expect 15-20 minutes
3. **Data errors**: Some symbols may have insufficient data (automatically skipped)
4. **Memory usage**: Large dataset may require 2-4GB RAM

### Performance Tips

- **Run during market hours** for most current data
- **Stable internet connection** recommended
- **Close other applications** to free up memory
- **Check progress messages** for real-time status

## Customization

### Modify Stock List
Edit `stock_symbols.py` to:
- Add/remove stocks from sector lists
- Adjust ETF selection
- Change total number of symbols

### Adjust Scoring
Edit `score_stock()` function in `us_stock_etf_scan.py` to:
- Modify point allocations
- Add new technical indicators
- Change thresholds

### Output Format
Modify Excel output sections to:
- Add new sheets
- Change column layouts
- Include additional metrics

## License

This project is for educational and research purposes. Please ensure compliance with data provider terms of service.
