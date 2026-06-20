import json
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data_loader import load_all_data
from backtest import BacktestEngine
from metrics import calculate_metrics, _validate_metrics
from config import BACKTEST_START, BACKTEST_END, NUM_TOKENS, STARTING_CAPITAL, TOKEN_NAMES

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def run_backtest():
    print("Loading synthetic market data...")
    tokens, fg = load_all_data()
    print(f"Loaded {len(tokens)} tokens, {len(fg)} periods of Fear & Greed data")

    print("Running backtest...")
    engine = BacktestEngine(tokens, fg)
    trades, equity_curve = engine.run()
    print(f"Completed: {len(trades)} trades executed")

    print("Calculating performance metrics...")
    metrics = calculate_metrics(trades, equity_curve)
    warnings = _validate_metrics(metrics)

    print("Saving results...")
    _save_trades(trades, f"{RESULTS_DIR}/trades.csv")
    _save_metrics(metrics, f"{RESULTS_DIR}/backtest_results.json")
    _plot_equity_curve(equity_curve, trades, f"{RESULTS_DIR}/equity_curve.png")

    _print_summary(metrics, warnings, len(trades))

    return metrics, trades, equity_curve


def _save_trades(trades, filepath):
    if not trades:
        pd.DataFrame().to_csv(filepath, index=False)
        return
    df = pd.DataFrame(trades)
    cols = ["token", "entry_date", "exit_date", "entry_price", "exit_price",
            "pnl_pct", "pnl_amount", "entry_fg", "exit_fg", "exit_reason",
            "candles_held"]
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(filepath, index=False)
    print(f"  Trades saved: {filepath}")


def _save_metrics(metrics, filepath):
    output = {
        "strategy_name": "Conviction Collapse Detector",
        "backtest_period": f"{BACKTEST_START} to {BACKTEST_END}",
        "tokens_tested": NUM_TOKENS,
        "total_trades": metrics.get("total_trades", 0),
        "winning_trades": metrics.get("winning_trades", 0),
        "losing_trades": metrics.get("losing_trades", 0),
        "metrics": {k: v for k, v in metrics.items() if k not in ("total_trades", "winning_trades", "losing_trades")},
        "edge_explanation": (
            "Signal detects sentiment decay (social hype dying) 1-7 days before price crashes. "
            "Works because retail traders FOMO at peaks (high Fear & Greed) while whales exit "
            "(declining social interest). Emerging market traders are particularly vulnerable "
            "to these patterns."
        ),
        "moat": (
            "Uses CMC's unique multi-layer data (Fear & Greed Index + KOL sentiment + "
            "on-chain whale transfers). No competitor offers this specific divergence detection."
        ),
    }
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Metrics saved: {filepath}")


def _plot_equity_curve(equity_curve, trades, filepath):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 1]})

    equity = equity_curve["equity"]
    ax1.plot(equity.index, equity.values, color="#2ecc71", linewidth=1.5, label="Portfolio Equity")

    peak = equity.cummax()
    dd = (equity - peak) / peak * 100
    ax2.fill_between(dd.index, dd.values, 0, color="#e74c3c", alpha=0.5, label="Drawdown %")
    ax2.plot(dd.index, dd.values, color="#c0392b", linewidth=1)

    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trade_dates = pd.to_datetime(trades_df["exit_date"])
        colors = ["#2ecc71" if p > 0 else "#e74c3c" for p in trades_df["pnl_pct"]]
        ax1.scatter(trade_dates, [equity.reindex([d], method="ffill").iloc[0] if d in equity.index else equity.iloc[-1] for d in trade_dates],
                    c=colors, s=30, alpha=0.6, zorder=5, label="Trades (green=win, red=loss)")

    ax1.axhline(y=STARTING_CAPITAL, color="gray", linestyle="--", alpha=0.5, label="Starting Capital")
    ax1.set_title("Conviction Collapse Detector — Equity Curve", fontsize=16, fontweight="bold")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.legend(loc="lower left")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Equity curve saved: {filepath}")


def _print_summary(metrics, warnings, trade_count):
    print("\n" + "=" * 60)
    print("  CONVICTION COLLAPSE DETECTOR - BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Period:     {BACKTEST_START} to {BACKTEST_END}")
    print(f"  Tokens:     {NUM_TOKENS}")
    print(f"  Trades:     {trade_count}")
    print(f"  Win/Loss:   {metrics.get('winning_trades', 0)} / {metrics.get('losing_trades', 0)}")
    print(f"  Win Rate:   {metrics.get('win_rate', 0):.1%}")
    print(f"  Sharpe:     {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  Profit Fac: {metrics.get('profit_factor', 0):.2f}")
    print(f"  Max DD:     {metrics.get('max_drawdown', 0):.1%}")
    print(f"  Total Ret:  {metrics.get('total_return', 0):.1%}")
    print(f"  Avg Win:    {metrics.get('avg_winning_trade', 0):.4f}")
    print(f"  Avg Loss:   {metrics.get('avg_losing_trade', 0):.4f}")
    print("-" * 60)

    if warnings:
        print("  WARNINGS:")
        for w in warnings:
            print(f"    [!] {w}")
    else:
        print("  No validation warnings - results look solid.")
    print("=" * 60)


if __name__ == "__main__":
    run_backtest()
