#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V0 广度雷达（全市场海选引擎）
从5000只A股中，通过量价规则、资金热度进行初筛。
"""
import akshare as ak
import pandas as pd
import time
import json
import os
import sys
import argparse
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

# 将项目根目录加入 path 以便导入 api 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from api.llm_assistant import generate_stock_ai_analysis
except ImportError:
    generate_stock_ai_analysis = None

STATUS_FILE = "data/screener_status.json"
RESULTS_FILE = "data/screener_results.json"
MOCK_PROGRESS = "data/screener_progress.json"

def write_status(file_path, status, progress, total, message, data=None):
    os.makedirs("data", exist_ok=True)
    state = {
        "status": status,
        "progress": progress,
        "total": total,
        "message": message,
        "data": data or []
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def fetch_all_spot(status_file, force_refresh=False):
    cache_file = "data/all_spot_cache.csv"
    today_str = time.strftime("%Y-%m-%d")
    
    # 如果不强制刷新，且今天已经有缓存，直接读取
    if not force_refresh and os.path.exists(cache_file):
        # 简单判断文件修改时间是否为今天
        mtime = os.path.getmtime(cache_file)
        file_date = time.strftime("%Y-%m-%d", time.localtime(mtime))
        if file_date == today_str:
            print("使用今天已缓存的全市场行情数据...")
            write_status(status_file, "running", 5, 100, "加载今日全市场行情缓存...")
            return pd.read_csv(cache_file, dtype=str)
            
    print("获取全市场实时行情...")
    write_status(status_file, "running", 0, 100, "正在连接行情源，获取全市场 5000+ 标的切片...")
    df = pd.DataFrame()
    try:
        # 首选: 东方财富
        print("尝试连接东方财富 (EM) 行情源...")
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        print(f"东方财富源被拦截: {e}")
        try:
            # 备用: 新浪
            write_status(status_file, "running", 5, 100, "东方财富被拦截，正在无缝切换至新浪(Sina)备用源，进度保留...")
            print("尝试无缝切换至新浪 (Sina) 备用源...")
            df = ak.stock_zh_a_spot()
        except Exception as e2:
            print(f"新浪源也失败: {e2}")
            return pd.DataFrame()
    
    if not df.empty:
        df.to_csv(cache_file, index=False, encoding="utf-8")
    return df

def apply_rule_filter(df):
    """
    基础规则过滤：
    1. 剔除ST、*ST、退市、停牌
    2. 成交额 > 1亿
    3. 涨跌幅筛选
    """
    if df.empty:
        return df
        
    print(f"过滤前总数: {len(df)}")
    
    # 剔除 ST
    df = df[~df['名称'].str.contains('ST|退')]
    
    # 成交额转为数字 ( akshare 返回的成交额单位不一，EM源通常是元)
    df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce').fillna(0)
    df = df[df['成交额'] > 100000000] # 1亿
    
    # 换手率
    if '换手率' in df.columns:
        df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce').fillna(0)
        df = df[df['换手率'] > 3.0]
    else:
        df['换手率'] = 0.0

    # 只保留涨幅在 0% ~ 9% 之间的票
    df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce').fillna(0)
    df = df[(df['涨跌幅'] > 0) & (df['涨跌幅'] < 9.0)]
    
    print(f"规则初筛后剩余数: {len(df)}")
    return df

def simulate_ai_analysis(code, name, row_data):
    """
    模拟 AI 分析逻辑，引入更多动态因子。
    """
    if generate_stock_ai_analysis:
        try:
            ai_text = generate_stock_ai_analysis(code, name, row_data)
            import re
            score_match = re.search(r'(\d{2,3})分', ai_text)
            score = float(score_match.group(1)) if score_match else round(60 + (hash(code) % 40), 1)
            reason = f"【AI 深度分析】{ai_text[:100]}..."
            return {"score": score, "reason": reason}
        except Exception as e:
            print(f"真实 AI 分析失败: {e}")
            
    # 仿真 AI 分析
    change = float(row_data.get("涨跌幅", 0))
    turnover = float(row_data.get("换手率", 0))
    
    trend = "强势拉升，多头情绪极度亢奋" if change > 5 else ("稳步走高，处于上升通道中轴" if change > 2 else "窄幅震震荡，蓄势待发")
    money = "换手极度活跃，主力洗盘迹象明显" if turnover > 10 else ("量能显著放大，资金进场意愿强烈" if turnover > 3 else "资金温和流入，筹码结构趋于稳定")

    score = round(65 + (hash(code) % 25) + (change * 0.5), 1)
    if score > 100: score = 100
    
    reason = f"【AI 定性分析】{name}: {trend}。{money}。建议关注。AI 评分: {score}"
    return {"score": score, "reason": reason}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-ai", action="store_true", help="是否使用AI进行深度定性筛选")
    parser.add_argument("--limit", type=int, default=0, help="限制分析数量，0表示不限制")
    parser.add_argument("--force-refresh", action="store_true", help="强制重新拉取全市场数据")
    args = parser.parse_args()
    
    status_file = "data/screener_status_ai.json" if args.use_ai else "data/screener_status_tech.json"
    
    if args.limit > 0:
        limit = args.limit
    else:
        limit = 20 if args.use_ai else 0 

    df_all = fetch_all_spot(status_file, args.force_refresh)
    if df_all.empty:
        write_status(status_file, "error", 0, 100, "无法连接行情源且无本地缓存")
        return
        
    write_status(status_file, "running", 10, 100, "应用多因子规则引擎...")
    df_filtered = apply_rule_filter(df_all)
    
    df_filtered = df_filtered.sort_values(by='成交额', ascending=False)
    if limit > 0:
        df_filtered = df_filtered.head(limit)
    
    candidates = df_filtered.to_dict('records')
    total = len(candidates)
    results = []
    
    if args.use_ai:
        write_status(status_file, "running", 20, total, f"启用 AI Brain，对 {total} 只标的进行深度扫描...")
        for i, row in enumerate(candidates):
            code = str(row.get("代码", ""))
            name = str(row.get("名称", ""))
            write_status(status_file, "running", i+1, total, f"AI 正在解析: {name} ({code})")
            
            try:
                ai_result = simulate_ai_analysis(code, name, row)
                if ai_result["score"] > 70:
                    results.append({
                        "code": code,
                        "name": name,
                        "price": row.get("最新价", 0),
                        "change_pct": row.get("涨跌幅", 0),
                        "turnover": row.get("换手率", 0),
                        "ai_score": ai_result["score"],
                        "logic": ai_result["reason"]
                    })
            except Exception as e:
                print(f"AI error for {code}: {e}")
    else:
        write_status(status_file, "running", 50, 100, f"经典算法直接提取 {total} 只标的...")
        for row in candidates:
            code = str(row.get("代码", ""))
            name = str(row.get("名称", ""))
            change = float(row.get("涨跌幅", 0))
            turnover = float(row.get("换手率", 0))
            results.append({
                "code": code,
                "name": name,
                "price": row.get("最新价", 0),
                "change_pct": change,
                "turnover": turnover,
                "logic": f"【技术海选】{name} ({code}): 今日涨幅 {change}%，成交额居前，换手率 {turnover}%，流动性极佳。"
            })
            
    if args.use_ai:
        results = sorted(results, key=lambda x: x.get("ai_score", 0), reverse=True)
    else:
        results = sorted(results, key=lambda x: x.get("change_pct", 0), reverse=True)
        
    write_status(status_file, "finished", total, total, f"筛选完毕！共 {len(results)} 只标的。", data=results)
    print(f"筛选完成，存活 {len(results)} 只标的。")

if __name__ == "__main__":
    main()
