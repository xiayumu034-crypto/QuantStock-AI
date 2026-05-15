import pandas as pd
import numpy as np
import akshare as ak
import sys
import os

# 将项目根目录加入 sys.path 以便导入 utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.afml.triple_barrier import get_daily_volatility, get_events, apply_triple_barrier

def main():
    stock_code = "000001"
    print(f"正在获取 {stock_code} 的历史数据...")
    df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date="20200101", end_date="20260501", adjust="qfq")
    df['日期'] = pd.to_datetime(df['日期'])
    df.set_index('日期', inplace=True)
    prices = df['收盘'].astype(float)
    
    print(f"共获取到 {len(prices)} 条数据，正在计算日波动率...")
    # 1. 计算日波动率 (span=100)
    volatility = get_daily_volatility(prices, span=100)
    
    # 2. 选取采样事件 (这里简化为每天都作为一个潜在的入场点 t_events)
    # 在 AFML 中，通常用对称 CUSUM 滤波器来提取有显著波动的点，为了简化演示，我们选取所有点
    t_events = prices.index
    
    # 3. 构建 events，设置垂直屏障 (例如持仓上限为 10 个交易日)
    num_days_limit = 10
    # 注意：这里的 events_df 构建函数需要交易日作为时间差，使用 pd.Timedelta(days=) 可能跨周末
    # 简单起见，我们直接在原 get_events 中基于索引位置推导
    
    # 重新定义一个简单的基于索引的 get_events 用于非日历连续的数据
    def get_events_idx(prices, t_events, target_vol, min_ret, num_bars):
        events = pd.DataFrame(index=t_events)
        # 获取索引的位置
        idx_positions = {idx: i for i, idx in enumerate(prices.index)}
        
        t1 = []
        for t in t_events:
            start_pos = idx_positions.get(t, -1)
            if start_pos != -1 and start_pos + num_bars < len(prices):
                t1.append(prices.index[start_pos + num_bars])
            else:
                t1.append(pd.NaT)
        
        events['t1'] = t1
        events['trgt'] = target_vol.loc[events.index]
        # 过滤低波动率
        events = events[events['trgt'] >= min_ret]
        return events

    events_df = get_events_idx(prices, t_events, volatility, min_ret=0.01, num_bars=10)
    
    print(f"共生成 {len(events_df)} 个符合最小波动率要求的事件，正在应用三重屏障...")
    
    # 4. 应用三重屏障 (pt_sl=[2, 1] 意味着止盈是波动率的 2 倍，止损是波动率的 1 倍)
    labels = apply_triple_barrier(
        prices=prices, 
        events=events_df, 
        pt_sl=[2.0, 1.0],  # 盈亏比 2:1
        target_vol=events_df['trgt']
    )
    
    # 5. 统计结果
    print("\n三重屏障打标签结果分布:")
    label_counts = labels['label'].value_counts().sort_index()
    print(f"止损 (-1) 次数: {label_counts.get(-1, 0)}")
    print(f"时间到期/未触达 (0) 次数: {label_counts.get(0, 0)}")
    print(f"止盈 (1) 次数: {label_counts.get(1, 0)}")
    
    win_rate = label_counts.get(1, 0) / (label_counts.get(1, 0) + label_counts.get(-1, 0) + 1e-9)
    print(f"\n胜率 (止盈 / (止盈+止损)): {win_rate:.2%}")
    print("\n(注：这只是单纯做多情况下的标签统计，说明在固定的盈亏比下，大部分交易可能触及止损或时间屏障)")

if __name__ == "__main__":
    main()