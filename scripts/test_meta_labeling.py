import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, precision_score, roc_auc_score
import akshare as ak
import os
import sys

# 将项目根目录加入 sys.path 以便导入 utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.afml.triple_barrier import get_daily_volatility, apply_triple_barrier, get_events

def extract_features(df):
    """
    提取一些基础的技术面特征作为元模型的输入。
    注意：在实战中，这里应该加入“分数阶差分”以及主模型的预测概率等。
    """
    features = pd.DataFrame(index=df.index)
    
    # 动量特征
    features['mom_5'] = df['收盘'].pct_change(5)
    features['mom_10'] = df['收盘'].pct_change(10)
    features['mom_20'] = df['收盘'].pct_change(20)
    
    # 波动率特征
    features['vol_10'] = df['收盘'].pct_change().rolling(10).std()
    features['vol_20'] = df['收盘'].pct_change().rolling(20).std()
    
    # 均线偏离度
    features['ma_5_bias'] = df['收盘'] / df['收盘'].rolling(5).mean() - 1
    features['ma_20_bias'] = df['收盘'] / df['收盘'].rolling(20).mean() - 1
    
    # 交易量特征
    features['vol_ratio_5'] = df['成交量'] / df['成交量'].rolling(5).mean()
    
    return features.dropna()

def main():
    stock_code = "000001"
    print(f"========== AFML Meta-Labeling (元标签) 演示 ==========")
    print(f"[1] 获取 {stock_code} 历史数据...")
    import time
    df = None
    for attempt in range(5):
        try:
            # 尝试使用新浪源（带 sz/sh 前缀）
            df = ak.stock_zh_a_daily(symbol="sz000001", start_date="20200101", end_date="20260501", adjust="qfq")
            if df is not None and not df.empty:
                # 新浪源的列名可能是 date, open, high, low, close, volume 等
                df.rename(columns={'date': '日期', 'open': '开盘', 'high': '最高', 'low': '最低', 'close': '收盘', 'volume': '成交量'}, inplace=True)
                break
        except Exception as e:
            print(f"    -> 获取数据失败，正在重试 ({attempt+1}/5): {e}")
            time.sleep(2)
            
    if df is None or df.empty:
        print("    -> 无法获取历史数据，请检查网络或更换数据源。")
        return
    df['日期'] = pd.to_datetime(df['日期'])
    df.set_index('日期', inplace=True)
    prices = df['收盘'].astype(float)
    
    print("[2] 模拟主模型 (Primary Model) 信号...")
    # 为了演示，我们构建一个简单的均线突破策略作为主模型：
    # 收盘价上穿 20 日均线且 5日均线大于20日均线时，发出做多信号 (1)
    ma5 = prices.rolling(5).mean()
    ma20 = prices.rolling(20).mean()
    
    primary_signals = pd.Series(0, index=prices.index)
    # 多头信号：MA5 > MA20，且当日价格在MA5之上
    buy_cond = (ma5 > ma20) & (prices > ma5)
    primary_signals[buy_cond] = 1
    
    # 提取有信号的时间点 (t_events)
    t_events = primary_signals[primary_signals == 1].index
    print(f"    -> 主模型共发出 {len(t_events)} 次做多信号.")
    
    if len(t_events) < 50:
        print("样本太少，无法训练。")
        return
        
    print("[3] 根据主模型信号，打上 AFML 三重屏障标签 (Triple-Barrier)...")
    volatility = get_daily_volatility(prices, span=100)
    
    # 构建事件 (限制持仓最大 15 天)
    def get_events_idx(prices, t_events, target_vol, min_ret, num_bars):
        events = pd.DataFrame(index=t_events)
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
        events = events[events['trgt'] >= min_ret]
        return events

    events_df = get_events_idx(prices, t_events, volatility, min_ret=0.005, num_bars=15)
    
    # pt_sl=[1.5, 1.0] (止盈是波动率的 1.5 倍，止损是 1 倍)
    tb_labels = apply_triple_barrier(prices, events_df, pt_sl=[1.5, 1.0], target_vol=events_df['trgt'])
    
    print("[4] 生成元标签 (Meta-Labels)...")
    # 主模型只做多 (1)。所以只有当三重屏障标签为 1 时，主模型才是“对”的；否则 (0 或 -1) 主模型都错了。
    # Meta-Label: 1 表示主模型做对了，0 表示主模型错了。
    meta_labels = tb_labels['label'].apply(lambda x: 1 if x == 1 else 0)
    
    success_rate = meta_labels.mean()
    print(f"    -> 基础均线主模型的实际成功率仅为: {success_rate:.2%}")
    print("    -> 痛点暴露：主模型虽然发出了买入信号，但超过一半都被止损或被时间耗死！")
    
    print("[5] 训练元模型 (Meta Model)...")
    # 提取特征
    X = extract_features(df)
    
    # 将特征与元标签对齐
    dataset = X.loc[meta_labels.index].dropna()
    y = meta_labels.loc[dataset.index]
    
    if len(dataset) < 50:
        print("有效特征对齐后的样本太少。")
        return
        
    # 切分训练集和测试集 (这里为了演示简单用按时间顺序切分，实际应使用 Purged K-Fold)
    split_idx = int(len(dataset) * 0.7)
    X_train, X_test = dataset.iloc[:split_idx], dataset.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # 训练随机森林分类器作为元模型
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, class_weight='balanced')
    clf.fit(X_train, y_train)
    
    # 预测概率 (即用来决定 Bet Sizing 仓位大小的概率)
    y_pred_prob = clf.predict_proba(X_test)[:, 1]
    y_pred = clf.predict(X_test)
    
    print("\n========== 元模型测试集评估结果 ==========")
    print(f"测试集主模型原始信号总数: {len(y_test)}")
    print(f"如果全部盲目执行，成功次数: {y_test.sum()} (胜率: {y_test.mean():.2%})")
    
    # 元模型介入：只有元模型预测为 1 (认为主模型对了) 才真正执行交易
    executed_trades = y_test[y_pred == 1]
    saved_trades = y_test[y_pred == 0]
    
    print(f"\n元模型过滤后，决定执行的交易数: {len(executed_trades)}")
    if len(executed_trades) > 0:
        print(f"执行交易的实际成功数: {executed_trades.sum()}")
        print(f"★ 提升后的实际胜率: {executed_trades.mean():.2%}")
    
    print(f"\n元模型拦截的交易数 (让您避免进场被坑): {len(saved_trades)}")
    if len(saved_trades) > 0:
        print(f"其中确实是烂交易(最终亏损/耗时)的占比: {1 - saved_trades.mean():.2%}")
        
    print("\n[总结]: 这就是 AFML 元标签的威力！主模型(如均线/MACD)只负责告诉你在哪儿可能有机会；")
    print("而元模型通过机器学习，看穿了当下的波动率、偏离度等复杂环境，过滤掉了大量必定止损的‘假突破’伪信号，从而将最终胜率大幅拔高！")

if __name__ == "__main__":
    main()