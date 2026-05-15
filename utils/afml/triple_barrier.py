import pandas as pd
import numpy as np

def get_daily_volatility(close_prices: pd.Series, span=100) -> pd.Series:
    """
    计算日波动率（Daily Volatility）
    基于对数收益率的指数加权移动标准差。
    AFML 建议使用此波动率来动态设置利润和止损的宽度。
    """
    # 计算每日对数收益率
    returns = np.log(close_prices / close_prices.shift(1))
    
    # 计算指数加权移动标准差 (EWM Std)
    # span 参数决定了历史数据衰减的速度
    ewm_std = returns.ewm(span=span).std()
    return ewm_std

def apply_triple_barrier(
    prices: pd.Series, 
    events: pd.DataFrame, 
    pt_sl: list = [1, 1], 
    target_vol: pd.Series = None, 
    min_ret: float = 0.005,
    num_threads: int = 1
) -> pd.DataFrame:
    """
    计算三重屏障标签 (Triple Barrier Method)
    
    参数:
    prices: pd.Series, 价格序列 (例如收盘价)
    events: pd.DataFrame, 包含 't1' (垂直屏障/时间到期日) 和 'trgt' (目标波动率/阈值)
    pt_sl: list, [利润因子, 止损因子], 与目标波动率相乘得到最终阈值。例如 [1.5, 1.0]
    target_vol: pd.Series, 给定时间点的目标波动率。
    min_ret: float, 最小触发收益率，如果目标波动率小于此值，则不计算。
    
    返回:
    pd.DataFrame, 包含 't1', 'trgt', 和 'label' (-1, 0, 1)
    """
    out = events[['t1']].copy()
    if target_vol is not None:
        out['trgt'] = target_vol
    else:
        out['trgt'] = events['trgt']

    # 输出标签列：-1 (触及止损), 1 (触及止盈), 0 (触及时间屏障或其他)
    out['label'] = 0
    out['end_time'] = out['t1']  # 实际结束的时间点

    pt = pt_sl[0] * out['trgt']
    sl = -pt_sl[1] * out['trgt']

    # 为了加速，我们在简单的循环或向量化中处理 (此处使用简单的逐行遍历，生产中可使用 Numba 或多线程)
    for loc, t1 in out['t1'].items():
        if pd.isna(t1):
            # 如果没有时间屏障，截取到序列末尾
            path = prices[loc:]
        else:
            path = prices[loc:t1]
            
        if len(path) <= 1:
            continue
            
        # 计算路径上的对数收益率 (相对于起点)
        path_ret = np.log(path / prices[loc])
        
        # 寻找第一次触碰上方屏障 (止盈)
        hit_pt = path_ret[path_ret > pt[loc]].index.min()
        # 寻找第一次触碰下方屏障 (止损)
        hit_sl = path_ret[path_ret < sl[loc]].index.min()
        
        earliest_hit = None
        label = 0
        
        if pd.notna(hit_pt) and pd.notna(hit_sl):
            if hit_pt < hit_sl:
                earliest_hit = hit_pt
                label = 1
            else:
                earliest_hit = hit_sl
                label = -1
        elif pd.notna(hit_pt):
            earliest_hit = hit_pt
            label = 1
        elif pd.notna(hit_sl):
            earliest_hit = hit_sl
            label = -1
        else:
            # 两个都没碰到，触及时间屏障
            earliest_hit = path.index[-1]
            label = 0
            
        out.loc[loc, 'label'] = label
        out.loc[loc, 'end_time'] = earliest_hit

    return out

def get_events(prices: pd.Series, t_events: pd.Index, pt_sl: list, target_vol: pd.Series, min_ret: float, num_days: int) -> pd.DataFrame:
    """
    构建 events DataFrame，主要是设置垂直屏障 (t1)。
    num_days: 持仓最大天数 (垂直屏障)
    """
    events = pd.DataFrame(index=t_events)
    # 计算垂直屏障 (T1)
    t1 = prices.index.searchsorted(t_events + pd.Timedelta(days=num_days))
    t1 = t1[t1 < len(prices)]
    # 处理超出范围的索引
    t1_series = pd.Series(prices.index[t1], index=t_events[:len(t1)])
    events['t1'] = t1_series
    
    # 过滤掉低于 min_ret 的目标波动率
    events['trgt'] = target_vol.loc[events.index]
    events = events[events['trgt'] >= min_ret]
    
    return events
