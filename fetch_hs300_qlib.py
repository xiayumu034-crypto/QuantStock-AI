#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib 数据管道适配器 (Phase 2 - 扩充至沪深300)
使用 Sina API 抓取沪深300成分股数据并转储为 Qlib 兼容的 CSV 格式。
"""

import akshare as ak
import pandas as pd
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8')

CSV_DUMP_DIR = "qlib_csv_dump"
os.makedirs(CSV_DUMP_DIR, exist_ok=True)

def fetch_and_format_for_qlib(stock_code):
    try:
        symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
        # 获取前复权日线数据 (2018年至今)
        df = ak.stock_zh_a_daily(symbol=symbol, start_date="20180101", end_date="20261231", adjust="hfq")
        if df.empty:
            return False, stock_code
            
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        # Sina的volume单位为股，amount单位为元
        df['vwap'] = df['amount'] / (df['volume'] + 1e-8)
        df['symbol'] = symbol
        
        cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'vwap', 'amount', 'turnover']
        df = df[cols]
        
        csv_path = os.path.join(CSV_DUMP_DIR, f"{symbol}.csv")
        df.to_csv(csv_path, index=False)
        return True, stock_code
    except Exception as e:
        print(f"抓取 {stock_code} 报错: {e}")
        return False, stock_code

if __name__ == "__main__":
    print("获取沪深300成分股列表...")
    try:
        hs300 = ak.index_stock_cons(symbol="399300")
        stock_list = hs300['品种代码'].tolist()
        print(f"成功获取 {len(stock_list)} 只成分股")
    except Exception as e:
        print(f"获取成分股失败: {e}")
        sys.exit(1)
        
    print("开始并发抓取历史数据...")
    success_count = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_and_format_for_qlib, code): code for code in stock_list}
        for idx, future in enumerate(as_completed(futures)):
            success, code = future.result()
            if success:
                success_count += 1
            if (idx + 1) % 10 == 0:
                print(f"已处理 {idx + 1}/{len(stock_list)} 只股票...")
                
    print(f"数据采集完成！成功: {success_count}/{len(stock_list)}")
