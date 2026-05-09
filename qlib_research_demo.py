#!/usr/bin/env python3
# -*- coding: utf-8 -*-

if __name__ == "__main__":
    import qlib
    from qlib.data import D
    from qlib.config import REG_CN
    import pandas as pd
    import os

    # 1. 初始化 Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/cn_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    print(f"[Qlib] 初始化成功，数据源路径: {provider_uri}")

    # 2. 查询系统内的日线股票
    instruments = D.instruments(market='all')
    stock_list = D.list_instruments(instruments=instruments, as_list=True)
    print(f"[Qlib] 系统内当前可用股票池: {stock_list}")

    # 3. 通过 Qlib 表达式极速计算因子特征
    features = {
        "CCI": "(($close - Mean($close, 14)) / (0.015 * Std($close, 14)))",
        "RSI_14": "100 - 100 / (1 + (Sum(If($close > Ref($close, 1), $close - Ref($close, 1), 0), 14) / Sum(If($close < Ref($close, 1), Ref($close, 1) - $close, 0), 14)))",
        "VWAP_ratio": "$vwap / $close",
        "Ret_5d": "Ref($close, -5)/$close - 1"
    }

    print("[Qlib] 正在生成量化因子与 Label...")
    fields = list(features.values())
    names = list(features.keys())
    df_features = D.features(stock_list, fields, start_time="2024-01-01", end_time="2026-12-31", freq='day')
    df_features.columns = names

    print("[Qlib] 特征工程执行完毕！以下是某只股票最近的 5 条特征快照：")
    print(df_features.groupby(level='instrument').tail(5).head(5))

    print("\n" + "="*50)
    print("🎉 恭喜！Qlib 特征引擎接入成功。")
    print("您现在可以看到，原本长达几十行的 Pandas 技术指标计算，现在在 Qlib 中仅仅是一行表达式。")
    print("下一步：我们可以直接把这个数据框 (df_features) 喂给 LightGBM 或者 Qlib 内置的模型进行策略训练和回测！")
    print("="*50)
