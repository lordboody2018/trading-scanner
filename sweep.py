import copy
import json
import os

from backtest import run_backtest

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
    base_cfg = json.load(f)

combos = [
    (1.0, 1.5),
    (1.2, 0.8),
    (1.5, 1.0),
    (1.5, 0.7),
    (2.0, 1.0),
]

print(f"{'SL':>4} {'TP':>4} | {'trades':>6} {'winrate':>8} {'pnl_R':>8}")
for sl_m, tp_m in combos:
    cfg = copy.deepcopy(base_cfg)
    cfg["sl_atr_mult"] = sl_m
    cfg["tp_atr_mult"] = tp_m
    r = run_backtest(cfg, bars=1500, verbose=False)
    print(f"{sl_m:>4} {tp_m:>4} | {r['trades']:>6} {str(r['win_rate'])+'%':>8} {r['pnl_r']:>8}")
