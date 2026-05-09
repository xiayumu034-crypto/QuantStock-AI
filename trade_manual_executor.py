#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vn.py 手工交易执行器
接收 Flask 发来的手工买卖指令，通过 vnpy 接口立即报单。
"""

import sys
import os
import json
import time
from datetime import datetime

# 强制终端使用 UTF-8 编码，防止 Windows 控制台打印 Emoji 报错
sys.stdout.reconfigure(encoding='utf-8')

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.constant import OrderType, Direction, Exchange
from vnpy.trader.object import OrderRequest
from vnpy.trader.gateway import BaseGateway

class MockAStockGateway(BaseGateway):
    """虚拟 A 股交易接口"""
    default_name = "MOCK_ASTOCK"
    
    def __init__(self, event_engine, gateway_name="MOCK_ASTOCK"):
        super().__init__(event_engine, gateway_name)
        
    def connect(self, setting: dict):
        self.write_log("连接到虚拟 A 股交易所成功！")
        
    def send_order(self, req: OrderRequest):
        orderid = f"MANUAL_{int(time.time()*1000)}"
        self.write_log(f"⚠️ [手工报单] 收到指令: {req.direction.value} {req.symbol} {req.volume}股")
        self.write_log(f"✅ 虚拟手工订单 {orderid} 已成交")
        return orderid

    def cancel_order(self, req):
        pass

    def subscribe(self, req):
        pass

    def query_account(self):
        pass

    def query_position(self):
        pass

    def close(self):
        pass

def main():
    if len(sys.argv) < 5:
        print("参数不足")
        return
        
    code = sys.argv[1]
    direction_str = sys.argv[2]
    price = float(sys.argv[3])
    volume = int(sys.argv[4])

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(MockAStockGateway)
    main_engine.connect({}, "MOCK_ASTOCK")

    exchange = Exchange.SSE if code.startswith("6") else Exchange.SZSE
    direction = Direction.LONG if direction_str == 'buy' else Direction.SHORT
    order_type = OrderType.LIMIT if price > 0 else OrderType.MARKET

    req = OrderRequest(
        symbol=code,
        exchange=exchange,
        direction=direction,
        type=order_type,
        volume=volume,
        price=price
    )
    
    order_id = main_engine.send_order(req, "MOCK_ASTOCK")
    
    # 写入交易日志供前端展示
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(base_dir, "model_output", "trade_logs.json")
    existing_logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                existing_logs = json.load(f)
        except Exception:
            pass
            
    # 新日志插在最前面
    existing_logs.insert(0, {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "code": code,
        "direction": "手工买入" if direction_str == 'buy' else "手工卖出",
        "volume": volume,
        "order_id": order_id,
        "status": "已成交(手工)"
    })
    existing_logs = existing_logs[:100]
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(existing_logs, f, ensure_ascii=False, indent=4)
        
    time.sleep(0.5)
    main_engine.close()

if __name__ == "__main__":
    main()
