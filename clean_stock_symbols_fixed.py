#!/usr/bin/env python3
"""
清理股票符号列表 - 修复版本
Clean Stock Symbols List - Fixed Version

这个脚本会：
1. 测试所有股票符号的数据可用性
2. 移除无法获取数据的符号（退市、合并、错误符号等）
3. 生成清理后的高质量股票符号列表
4. 保存为新的 stock_symbols_clean.py 文件
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import json
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

def clean_symbol_list(symbols, symbol_type="股票"):
    """清理符号列表"""
    print(f"\n🧹 开始清理{symbol_type}符号列表...")
    print(f"原始{symbol_type}数量: {len(symbols)}")
    
    valid_symbols = []
    invalid_symbols = []
    
    for i, symbol in enumerate(symbols):
        # 进度显示
        if (i + 1) % 50 == 0 or (i + 1) == len(symbols):
            print(f"📈 进度: {i + 1}/{len(symbols)} ({(i + 1)/len(symbols)*100:.1f}%)")
        
        is_valid, reason = test_symbol_data_quality(symbol)
        
        if is_valid:
            valid_symbols.append(symbol)
            if len(valid_symbols) <= 10:  # 只显示前10个有效符号的详情
                print(f"✅ {symbol}: 数据质量良好")
        else:
            invalid_symbols.append((symbol, reason))
            if len(invalid_symbols) <= 10:  # 只显示前10个无效符号的详情
                print(f"❌ {symbol}: {reason}")
        
        # 避免请求过于频繁
        time.sleep(0.1)
    
    print(f"\n📊 {symbol_type}清理结果:")
    print(f"   - 有效{symbol_type}: {len(valid_symbols)}")
    print(f"   - 无效{symbol_type}: {len(invalid_symbols)}")
    print(f"   - 数据质量: {len(valid_symbols)/len(symbols)*100:.1f}%")
    
    if invalid_symbols:
        print(f"\n❌ 无效{symbol_type}列表 (前20个):")
        for symbol, reason in invalid_symbols[:20]:
            print(f"   - {symbol}: {reason}")
        
        if len(invalid_symbols) > 20:
            print(f"   ... 还有 {len(invalid_symbols) - 20} 个无效{symbol_type}")
    
    return valid_symbols, invalid_symbols

def main():
    print("🚀 开始清理股票符号列表...")
    print("=" * 60)
    
    start_time = datetime.now()
    
    # 清理股票符号
    valid_stocks, invalid_stocks = clean_symbol_list(STOCK_SYMBOLS, "股票")
    
    # 清理ETF符号
    valid_etfs, invalid_etfs = clean_symbol_list(ETF_SYMBOLS, "ETF")
    
    # 生成清理后的文件内容
    file_content = f'''#!/usr/bin/env python3
"""
清理后的美国股票和ETF符号列表
Cleaned US Stock and ETF Symbols List

清理日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
原始股票数量: {len(STOCK_SYMBOLS)} -> 清理后: {len(valid_stocks)}
原始ETF数量: {len(ETF_SYMBOLS)} -> 清理后: {len(valid_etfs)}
数据质量: 股票 {len(valid_stocks)/len(STOCK_SYMBOLS)*100:.1f}%, ETF {len(valid_etfs)/len(ETF_SYMBOLS)*100:.1f}%
"""

# 清理后的股票符号列表 ({len(valid_stocks)} 个高质量股票)
STOCK_SYMBOLS = {repr(valid_stocks)}

# 清理后的ETF符号列表 ({len(valid_etfs)} 个高质量ETF)
ETF_SYMBOLS = {repr(valid_etfs)}

# 无效股票符号记录 (供参考)
INVALID_STOCKS = {repr([symbol for symbol, reason in invalid_stocks])}

# 无效ETF符号记录 (供参考)
INVALID_ETFS = {repr([symbol for symbol, reason in invalid_etfs])}

if __name__ == "__main__":
    print(f"📊 清理后的符号统计:")
    print(f"   - 有效股票: {{len(STOCK_SYMBOLS)}} 个")
    print(f"   - 有效ETF: {{len(ETF_SYMBOLS)}} 个")
    print(f"   - 总计: {{len(STOCK_SYMBOLS) + len(ETF_SYMBOLS)}} 个高质量符号")
    print(f"   - 无效股票: {{len(INVALID_STOCKS)}} 个")
    print(f"   - 无效ETF: {{len(INVALID_ETFS)}} 个")
'''
    
    # 保存清理后的文件
    output_file = "stock_symbols_clean.py"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    # 保存详细的清理报告
    report = {
        "清理时间": datetime.now().isoformat(),
        "原始统计": {
            "股票数量": len(STOCK_SYMBOLS),
            "ETF数量": len(ETF_SYMBOLS),
            "总数量": len(STOCK_SYMBOLS) + len(ETF_SYMBOLS)
        },
        "清理后统计": {
            "有效股票": len(valid_stocks),
            "有效ETF": len(valid_etfs),
            "总有效数量": len(valid_stocks) + len(valid_etfs)
        },
        "无效符号": {
            "无效股票": [{"symbol": symbol, "reason": reason} for symbol, reason in invalid_stocks],
            "无效ETF": [{"symbol": symbol, "reason": reason} for symbol, reason in invalid_etfs]
        },
        "数据质量": {
            "股票质量": f"{len(valid_stocks)/len(STOCK_SYMBOLS)*100:.1f}%",
            "ETF质量": f"{len(valid_etfs)/len(ETF_SYMBOLS)*100:.1f}%",
            "总体质量": f"{(len(valid_stocks) + len(valid_etfs))/(len(STOCK_SYMBOLS) + len(ETF_SYMBOLS))*100:.1f}%"
        }
    }
    
    with open("symbol_cleaning_report.json", 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print("✅ 符号列表清理完成!")
    print(f"📁 清理后的文件: {output_file}")
    print(f"📄 详细报告: symbol_cleaning_report.json")
    print(f"⏱️  总用时: {total_time/60:.1f} 分钟")
    print("\n📊 最终统计:")
    print(f"   - 原始符号: {len(STOCK_SYMBOLS) + len(ETF_SYMBOLS)} 个")
    print(f"   - 有效符号: {len(valid_stocks) + len(valid_etfs)} 个")
    print(f"   - 移除符号: {len(invalid_stocks) + len(invalid_etfs)} 个")
    print(f"   - 数据质量: {(len(valid_stocks) + len(valid_etfs))/(len(STOCK_SYMBOLS) + len(ETF_SYMBOLS))*100:.1f}%")
    print("\n🎯 现在可以使用 stock_symbols_clean.py 进行高质量的股票扫描!")

if __name__ == "__main__":
    main()