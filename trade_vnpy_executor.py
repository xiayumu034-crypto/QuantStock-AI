#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vn.py 信号执行器 (实盘/模拟盘 网关)
连接 Qlib 产生的 daily_predictions.json 信号，通过 vnpy 发送实盘或模拟盘交易指令。
"""

import json
import os
import sys
import time
from datetime import datetime

# 强制终端使用 UTF-8 编码，防止 Windows 控制台打印 Emoji 报错
sys.stdout.reconfigure(encoding='utf-8')

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.constant import OrderType, Direction, Exchange
from vnpy.trader.object import OrderRequest

# 实际生产中应引入真实的实盘网关（如 QMT, XTP, CTP）
# 比如：from vnpy_qmt import QmtGateway 
# 这里为了演示架构，我们定义一个轻量级的 Mock 网关，防止真的把钱亏了
from vnpy.trader.gateway import BaseGateway

class MockAStockGateway(BaseGateway):
    """虚拟 A 股交易接口 (防止测试时发生真实资金风险)"""
    
    default_name = "MOCK_ASTOCK"
    
    def __init__(self, event_engine, gateway_name="MOCK_ASTOCK"):
        super().__init__(event_engine, gateway_name)
        self.orders = {}
        
    def connect(self, setting: dict):
        self.write_log("连接到虚拟 A 股交易所成功！")
        
    def send_order(self, req: OrderRequest):
        orderid = f"MOCK_{int(time.time()*1000)}"
        self.write_log(f"⚠️ [实盘网关拦截] 收到下单指令: {req.direction.value} {req.symbol} {req.volume}股 (价格: {req.price})")
        self.write_log(f"✅ 虚拟订单 {orderid} 报单成功")
        return orderid

    def cancel_order(self, req):
        self.write_log(f"撤单请求: {req.orderid}")

    def subscribe(self, req):
        self.write_log(f"虚拟订阅行情: {req.symbol}")

    def query_account(self):
        pass

    def query_position(self):
        pass

    def close(self):
        self.write_log("虚拟接口已关闭")


def run_trading_executor():
    # 使用绝对路径防止 vnpy 初始化时改变工作目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    signal_file = os.path.join(base_dir, "model_output", "daily_predictions.json")
    
    print("="*60)
    print("🚀 [vn.py 交易执行器] 启动")
    print("="*60)
    
    if not os.path.exists(signal_file):
        print(f"❌ 找不到信号文件: {signal_file}，请先执行 Qlib 离线推理。")
        return

    # 1. 初始化 vn.py 事件引擎和主引擎
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    
    # 2. 添加交易网关 (替换为真实券商网关即可实盘)
    main_engine.add_gateway(MockAStockGateway)
    main_engine.connect({}, "MOCK_ASTOCK")
    
    # 3. 读取 Qlib 输出的每日预测信号
    with open(signal_file, 'r', encoding='utf-8') as f:
        predictions = json.load(f)
        
    print(f"📊 加载信号成功，共扫描 {len(predictions)} 只标的。")
    time.sleep(1) # 模拟网络延迟
    
    # 4. 执行交易策略
    trade_logs = []
    for code, data in predictions.items():
        signal = data.get("signal")
        confidence = data.get("confidence", 0)
        
        # 将 A 股代码转换为 vn.py 的统一命名规则
        exchange = Exchange.SSE if code.startswith("6") else Exchange.SZSE
        
        # 简单策略：看涨买入，看跌卖出
        if signal == "bullish" and confidence > 0.8:
            print(f"\n[买入信号] {code} 置信度: {confidence} -> 触发建仓！")
            
            req = OrderRequest(
                symbol=code,
                exchange=exchange,
                direction=Direction.LONG,
                type=OrderType.MARKET, # 市价单
                volume=100,           # 买入 1手 (100股)
                price=0               # 市价单无需指定价格
            )
            order_id = main_engine.send_order(req, "MOCK_ASTOCK")
            trade_logs.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "code": code,
                "direction": "买入",
                "volume": 100,
                "order_id": order_id,
                "status": "已报单"
            })
            
        elif signal == "bearish" and confidence > 0.8:
            print(f"\n[卖出信号] {code} 置信度: {confidence} -> 触发清仓！")
            
            req = OrderRequest(
                symbol=code,
                exchange=exchange,
                direction=Direction.SHORT,
                type=OrderType.MARKET,
                volume=100,
                price=0
            )
            order_id = main_engine.send_order(req, "MOCK_ASTOCK")
            trade_logs.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "code": code,
                "direction": "卖出",
                "volume": 100,
                "order_id": order_id,
                "status": "已报单"
            })
            
    print("\n✅ 所有量化信号执行完毕，等待收盘。")
    
    # 写入交易日志供前端展示
    log_file = os.path.join(base_dir, "model_output", "trade_logs.json")
    # 保留历史日志，最多100条
    existing_logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                existing_logs = json.load(f)
        except:
            pass
    existing_logs = trade_logs + existing_logs
    existing_logs = existing_logs[:100]
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(existing_logs, f, ensure_ascii=False, indent=4)
    
    # 清理并退出事件引擎，防止进程挂起
    time.sleep(1)
    main_engine.close()
    
if __name__ == "__main__":
    run_trading_executor()
