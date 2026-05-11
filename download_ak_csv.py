import json
import os
import time
import pandas as pd
import akshare as ak

def download_data():
    os.makedirs('csv_data', exist_ok=True)
    
    # 获取精选股票池
    stock_pool = []
    if os.path.exists('../data/curated_stocks_v12.json'):
        with open('../data/curated_stocks_v12.json', 'r', encoding='utf-8') as f:
            stock_pool = json.load(f)
    elif os.path.exists('data/stock_names.json'):
        with open('data/stock_names.json', 'r', encoding='utf-8') as f:
            stocks = json.load(f)
            stock_pool = list(stocks.keys())[:54] # fall back
            
    print(f"准备下载 {len(stock_pool)} 只股票数据...")
    
    for code in stock_pool:
        # AKShare 接口
        clean_code = code[-6:]
        prefix = "sh" if clean_code.startswith("6") else "sz"
        qlib_code = f"{prefix}{clean_code}"
        
        try:
            print(f"Downloading {qlib_code}...")
            # 下载 qfq 数据
            df = ak.stock_zh_a_daily(symbol=qlib_code, start_date="20050101", adjust="qfq")
            if df is None or df.empty:
                print(f"  No data for {qlib_code}")
                continue
                
            # 格式化成 Qlib 所需格式
            # date, open, close, high, low, volume, amount
            df.rename(columns={'date': 'date'}, inplace=True)
            df = df[['date', 'open', 'close', 'high', 'low', 'volume', 'amount']]
            # AKshare volume is in lots (100 shares), amount is in RMB.
            # We don't need to scale them unless we want absolute values, Qlib normalizes them.
            
            # Save CSV
            csv_path = f"csv_data/{qlib_code}.csv"
            df.to_csv(csv_path, index=False)
            time.sleep(0.5)  # 避免被限流
            
        except Exception as e:
            print(f"Error downloading {qlib_code}: {e}")

if __name__ == "__main__":
    download_data()