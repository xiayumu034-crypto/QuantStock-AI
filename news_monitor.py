#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时新闻监控模块
数据源: 财联社 + 东方财富 + 同花顺
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import akshare as ak
import pandas as pd
from datetime import datetime

POSITIVE_KEYWORDS = [
    '利好', '大涨', '涨停', '突破', '创新高', '增长', '盈利', '超预期',
    '订单', '中标', '签约', '合作', '回购', '增持', '业绩预增', '新高',
]

NEGATIVE_KEYWORDS = [
    '利空', '大跌', '跌停', '暴跌', '亏损', '下滑', '减持', '质押',
    '违规', '处罚', '调查', '退市', '风险', '警告', '业绩预减', '暴雷',
]

STOCK_KEYWORDS = {
    '300201': ['海伦哲', '300201'],
    '000001': ['平安银行', '000001'],
    '600519': ['贵州茅台', '600519', '茅台', '白酒'],
    '300750': ['宁德时代', '300750', '宁德', '锂电'],
    '002594': ['比亚迪', '002594', '比亚迪', '新能源车'],
}


def fetch_all_news():
    """获取所有新闻源"""
    all_news = []
    
    # 财联社
    try:
        df = ak.stock_info_global_cls()
        if df is not None:
            for _, row in df.iterrows():
                all_news.append({
                    'source': '财联社', 'title': str(row.get('标题', '')),
                    'content': str(row.get('内容', '')),
                    'time': f"{row.get('发布日期', '')} {row.get('发布时间', '')}",
                })
    except Exception as e:
        print(f"财联社: {e}")
    
    # 东方财富
    try:
        df = ak.stock_info_global_em()
        if df is not None:
            for _, row in df.head(50).iterrows():
                all_news.append({
                    'source': '东方财富', 'title': str(row.get('标题', '')),
                    'content': str(row.get('摘要', '')), 'time': str(row.get('发布时间', '')),
                })
    except Exception as e:
        print(f"东方财富: {e}")
    
    # 同花顺
    try:
        df = ak.stock_info_global_ths()
        if df is not None:
            for _, row in df.iterrows():
                all_news.append({
                    'source': '同花顺', 'title': str(row.get('内容', '')),
                    'content': str(row.get('内容', '')), 'time': str(row.get('发布时间', '')),
                })
    except Exception as e:
        print(f"同花顺: {e}")
    
    return all_news


def analyze_news(all_news):
    """分析新闻情绪"""
    analyzed = []
    for news in all_news:
        text = f"{news['title']} {news['content']}"
        pos = [kw for kw in POSITIVE_KEYWORDS if kw in text]
        neg = [kw for kw in NEGATIVE_KEYWORDS if kw in text]
        score = len(pos) - len(neg)
        
        related = []
        for code, kws in STOCK_KEYWORDS.items():
            hits = [kw for kw in kws if kw in text]
            if hits:
                related.append({'code': code, 'keywords': hits})
        
        news['sentiment_score'] = score
        news['sentiment'] = '利好' if score > 0 else ('利空' if score < 0 else '中性')
        news['related_stocks'] = related
        news['is_important'] = abs(score) >= 2 or len(related) > 0
        analyzed.append(news)
    
    analyzed.sort(key=lambda x: (x['is_important'], abs(x['sentiment_score'])), reverse=True)
    return analyzed


if __name__ == '__main__':
    print("获取新闻...")
    news = fetch_all_news()
    print(f"共获取 {len(news)} 条新闻")
    
    analyzed = analyze_news(news)
    important = [n for n in analyzed if n['is_important']]
    print(f"重大新闻 {len(important)} 条:\n")
    
    for n in important[:10]:
        icon = '🟢' if n['sentiment'] == '利好' else ('🔴' if n['sentiment'] == '利空' else '⚪')
        stocks = ','.join(s['code'] for s in n['related_stocks']) if n['related_stocks'] else ''
        print(f"{icon} [{n['source']}] {n['title'][:60]}")
        if stocks:
            print(f"   关联: {stocks}")
        print()
