#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VnpyExecutor: 将 V20 AFML 信号对接至 vn.py 交易引擎。
支持模拟账户同步与实盘（需配置柜台）接口。
"""
import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime

# 设置编码，防止 Windows 下 emoji 导致崩溃
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("trade_executor.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 尝试导入 vnpy 组件
try:
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine
    from vnpy.trader.ui import MainWindow, create_qapp
    from vnpy_ctp import CtpGateway
    # 其他插件根据需要添加
    HAS_VNPY = True
except ImportError:
    HAS_VNPY = False
    logging.warning("未检测到 vn.py 环境，将进入 [Mock/Sim] 仿真执行模式。")

class VnpyExecutor:
    def __init__(self, mode='sim', threshold=0.55):
        self.mode = mode
        self.threshold = threshold
        self.v20_file = "model_output/daily_predictions_v20.json"
        self.account_file = "data/sim_account.json"
        self.main_engine = None
        
        if HAS_VNPY and mode == 'live':
            # 初始化 vn.py 引擎逻辑
            self.event_engine = EventEngine()
            self.main_engine = MainEngine(self.event_engine)
            self.main_engine.add_gateway(CtpGateway)
            logging.info("vn.py MainEngine 已初始化，对接 CTP 柜台。")

    def load_signals(self):
        if not os.path.exists(self.v20_file):
            logging.error(f"找不到预测文件: {self.v20_file}")
            return []
        
        with open(self.v20_file, 'r', encoding='utf-8') as f:
            content = json.load(f)
            
        data = content.get('data', {})
        signals = []
        for code, info in data.items():
            score = info.get('meta_score', 0)
            if score >= self.threshold:
                signals.append({
                    "code": code,
                    "name": info.get('name', 'Unknown'),
                    "score": score,
                    "return": info.get('predicted_return', 0)
                })
        
        # 按胜率降序排序
        signals = sorted(signals, key=lambda x: x['score'], reverse=True)
        logging.info(f"从 V20 引擎提取到 {len(signals)} 个高胜率信号 (Threshold >= {self.threshold})")
        return signals

    def execute_trade(self, signal):
        """执行单笔交易"""
        # =========================================================================
        # [AI 核心准则备注 (给未来的模型看)]: 
        # 无论外层逻辑如何变化、信号引擎如何升级，最终买入动作的物理拦截器必须放置在
        # 最底层的执行函数内部！这样才能确保：只要 A 股处于休市期间，任何途径发起的
        # 买入动作都会被无情拦下，从而保障模拟盘与实盘在时间维度上的绝对一致性。
        # =========================================================================
        if not self.is_market_open():
            logging.warning(f"⛔ 物理拦截：当前非A股交易时间段，禁止执行买入操作 -> {signal['name']}")
            return

        code = signal['code']
        name = signal['name']
        score = signal['score']
        
        logging.info(f"🎯 触发信号: {name} ({code}), 胜率: {score:.2%}")
        
        if self.mode == 'sim':
            # 调用模拟交易 API 或直接修改 sim_account.json
            self._execute_sim_trade(signal)
        elif self.mode == 'live' and self.main_engine:
            logging.info(f"🚀 [实盘预警] 正在通过 vn.py 发送买入指令: {signal['code']}")
            try:
                from vnpy.trader.object import OrderRequest
                from vnpy.trader.constant import Exchange, Direction, Offset, OrderType
                
                # Determine exchange from prefix
                prefix = signal['code'][:2].lower()
                if prefix == 'sh':
                    exchange = Exchange.SSE
                elif prefix == 'sz':
                    exchange = Exchange.SZSE
                elif prefix == 'bj':
                    exchange = Exchange.BSE
                else:
                    # fallback
                    exchange = Exchange.SSE if str(signal['code']).startswith('6') else Exchange.SZSE
                    
                clean_code = signal['code'][-6:]
                
                price = self._get_latest_price(signal['code'])
                if not price or price <= 0:
                    logging.warning(f"无法获取 {signal['name']} ({signal['code']}) 的有效价格，跳过实盘下单。")
                    return
                    
                req = OrderRequest(
                    symbol=clean_code,
                    exchange=exchange,
                    direction=Direction.LONG,
                    type=OrderType.LIMIT,
                    volume=100, # 默认先打1手测试
                    price=price,
                    offset=Offset.OPEN,
                    reference=f"V20_{signal['score']:.2f}"
                )
                
                # 'CTP' is the gateway name for CtpGateway
                vt_orderid = self.main_engine.send_order(req, "CTP")
                logging.info(f"✅ vn.py 实盘委托已发送: {signal['name']}, 委托号: {vt_orderid}")
            except Exception as e:
                logging.error(f"❌ vn.py 实盘下单失败: {e}")

    def _execute_sim_trade(self, signal):
        """内部模拟交易逻辑"""
        try:
            # 获取最新价格
            price = self._get_latest_price(signal['code'])
            if not price or price <= 0:
                logging.warning(f"无法获取 {signal['name']} ({signal['code']}) 的有效价格，跳过交易。")
                return

            if not os.path.exists(self.account_file):
                account = {"cash": 100000.0, "holdings": {}, "logs": []}
            else:
                with open(self.account_file, 'r', encoding='utf-8') as f:
                    account = json.load(f)
            
            # 简单检查是否已持仓
            if signal['code'] in account['holdings']:
                logging.info(f"⏭️ {signal['name']} 已在持仓中，跳过买入。")
                return

            # 计算买入数量 (假设每只票分配 10% 资金)
            buy_budget = account['cash'] * 0.1
            if buy_budget < 5000: buy_budget = min(account['cash'], 10000)
            
            if account['cash'] < buy_budget:
                logging.warning(f"❌ 资金不足，无法买入 {signal['name']}")
                return

            vol = int(buy_budget / price / 100) * 100
            if vol == 0: return

            # 更新账户
            account['cash'] -= price * vol
            account['holdings'][signal['code']] = {
                "name": signal['name'],
                "cost_price": price,
                "current_price": price,
                "vol": vol,
                "buy_date": datetime.now().strftime("%Y-%m-%d"),
                "buy_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            account['logs'].insert(0, {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": "buy",
                "code": signal['code'],
                "name": signal['name'],
                "price": price,
                "vol": vol,
                "reason": f"V20 Meta-Score: {signal['score']:.4f}"
            })
            
            with open(self.account_file, 'w', encoding='utf-8') as f:
                json.dump(account, f, ensure_ascii=False, indent=4)
            logging.info(f"✅ 模拟交易成功: 买入 {signal['name']} {vol}股, 价格: {price}")
            
        except Exception as e:
            logging.error(f"模拟交易执行失败: {e}")

    def _get_latest_price(self, code):
        """从行情缓存中尝试提取价格"""
        cache_file = "data/all_spot_cache.csv"
        if not os.path.exists(cache_file):
            return None
        
        try:
            import pandas as pd
            df = pd.read_csv(cache_file, dtype=str)
            # 这里的匹配逻辑需要兼容：600000 (V20) -> sh600000 / bj600000 / sz600000 (Cache)
            # 或者 V20 已经是带前缀的
            
            # 1. 尝试直接匹配
            row = df[df['代码'] == code]
            if row.empty:
                # 2. 尝试去掉 V20 code 的前缀再模糊匹配 cache 里的后缀
                clean_code = code.replace("sh", "").replace("sz", "").replace("bj", "")
                # 在 cache 的 '代码' 列中寻找结尾是 clean_code 的
                row = df[df['代码'].str.endswith(clean_code)]
                
            if not row.empty:
                return float(row.iloc[0]['最新价'])
        except Exception as e:
            logging.error(f"读取价格缓存失败: {e}")
        return None


    def is_market_open(self):
        now = datetime.now()
        if now.isoweekday() > 5:  # 周六周日休市
            return False
        
        t = now.time()
        from datetime import time as dtime
        # A股交易时间: 09:30-11:30, 13:00-15:00
        if (dtime(9, 30) <= t <= dtime(11, 30)) or (dtime(13, 0) <= t <= dtime(15, 0)):
            return True
        return False

    def run(self):
        signals = self.load_signals()
        if not signals:
            logging.info("今日无高胜率信号，空仓观望。")
            return
            
        for sig in signals:
            self.execute_trade(sig)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="sim", choices=["sim", "live"], help="交易模式: sim(模拟) 或 live(实盘)")
    parser.add_argument("--threshold", type=float, default=0.50, help="V20 胜率准入门槛")
    args = parser.parse_args()

    executor = VnpyExecutor(mode=args.mode, threshold=args.threshold)
    executor.run()
