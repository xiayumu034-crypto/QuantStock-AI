#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib 数据管道适配器 (Phase 1)
将 AkShare 抓取的 A 股数据转储为 Qlib 兼容的 CSV 格式，并提示后续的 Dump 操作。
"""

import akshare as ak
import pandas as pd
import os
from datetime import datetime

# Qlib 数据存储的 CSV 中转目录
CSV_DUMP_DIR = "qlib_csv_dump"
os.makedirs(CSV_DUMP_DIR, exist_ok=True)

def fetch_and_format_for_qlib(stock_code):
    print(f"正在抓取 {stock_code} 的日线数据，准备适配 Qlib...")
    try:
        # 获取前复权日线数据
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date="20100101", end_date="20261231", adjust="hfq")
        if df.empty:
            return False
            
        # Qlib 要求的列名映射
        # 必须包含: date, open, high, low, close, volume, vwvwap/amount 等
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "change",
            "换手率": "turnover"
        })
        
        # 确保时间格式正确
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # 计算 VWAP (量价加权平均价) 作为一个因子
        df['vwap'] = df['amount'] / (df['volume'] * 100 + 1e-8)
        
        # Qlib 要求的 Symbol 格式: sh600519 或 sz000001
        symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
        df['symbol'] = symbol
        
        # 保持需要的列
        cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'vwap', 'amount', 'turnover']
        df = df[cols]
        
        # 写入 CSV
        csv_path = os.path.join(CSV_DUMP_DIR, f"{symbol}.csv")
        df.to_csv(csv_path, index=False)
        print(f"[成功] {symbol} 数据已保存至 {csv_path}")
        return True
    except Exception as e:
        print(f"[失败] 抓取 {stock_code} 报错: {e}")
        return False

if __name__ == "__main__":
    # 测试转化几只核心股票
    test_stocks = ["000001", "600519", "300750", "002594", "300201"]
    for code in test_stocks:
        fetch_and_format_for_qlib(code)
        
    print("\n" + "="*50)
    print("✅ 第一阶段：数据采集与 Qlib CSV 格式化完成！")
    print("下一步操作指南：")
    print("1. 因为 Qlib 依赖底层的 C++ 编译和旧版本 pyarrow，请在独立的虚拟环境中安装: `pip install pyqlib`")
    print("2. 使用 Qlib 的官方转储脚本将上述 CSV 转换为高效的 .bin 格式：")
    print(f"   python -m qlib.scripts.dump_bin dump_all --csv_path ./{CSV_DUMP_DIR} --qlib_dir ~/.qlib/qlib_data/cn_data --freq day --date_field_name date")
    print("="*50)