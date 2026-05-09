#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
向后兼容包装器。
实际评估逻辑已迁移至 evaluate_model.py。
为防止外部定时任务或旧脚本调用失败，保留此文件。
"""

import sys
from evaluate_model import evaluate_predictions

if __name__ == "__main__":
    print("[Warn] evaluate_model_v17.py 已废弃，推荐使用 evaluate_model.py --version v17")
    evaluate_predictions(version="v17")
