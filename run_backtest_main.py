import json
import os

from backtest import run_backtest


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    results = run_backtest(cfg, bars=1500, verbose=True)

    print("\n================ TOTAL ================")
    print(f"Trades:      {results['trades']}")
    print(f"Wins:        {results['wins']}")
    print(f"Losses:      {results['losses']}")
    print(f"Win rate:    {results['win_rate']}%")
    print(f"PnL (R):     {results['pnl_r']}")
    print(f"Avg R/trade: {results['avg_r']}")


if __name__ == "__main__":
    main()
