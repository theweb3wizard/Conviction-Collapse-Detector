import numpy as np
import pandas as pd
from config import STARTING_CAPITAL


def calculate_metrics(trades, equity_curve):
    if len(trades) < 1:
        return {"error": "no trades executed"}

    daily_returns = equity_curve["equity"].pct_change().dropna().values
    if len(daily_returns) < 2:
        return {"error": "insufficient equity curve data"}

    sharp_ratio = _calc_sharpe(daily_returns)

    winning = [t for t in trades if t["pnl_pct"] > 0]
    losing = [t for t in trades if t["pnl_pct"] <= 0]

    gross_profit = sum(t["pnl_amount"] for t in winning)
    gross_loss = abs(sum(t["pnl_amount"] for t in losing)) if losing else 1e-10
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float("inf")

    win_rate = len(winning) / len(trades) if trades else 0
    max_dd = _calc_max_drawdown(equity_curve["equity"].values)
    total_return = (equity_curve["equity"].iloc[-1] - STARTING_CAPITAL) / STARTING_CAPITAL

    avg_win = np.mean([t["pnl_pct"] for t in winning]) if winning else 0
    avg_loss = np.mean([t["pnl_pct"] for t in losing]) if losing else 0

    metrics = {
        "sharpe_ratio": round(sharp_ratio, 4),
        "profit_factor": round(profit_factor, 4),
        "win_rate": round(win_rate, 4),
        "max_drawdown": round(max_dd, 4),
        "total_return": round(total_return, 4),
        "avg_winning_trade": round(avg_win, 6),
        "avg_losing_trade": round(avg_loss, 6),
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
    }

    _validate_metrics(metrics)
    return metrics


def _calc_sharpe(daily_returns):
    if len(daily_returns) < 5:
        return 0.0
    mean_ret = np.mean(daily_returns)
    std_ret = np.std(daily_returns, ddof=1)
    if std_ret == 0 or np.isnan(std_ret):
        return 0.0
    return (mean_ret / std_ret) * np.sqrt(252)


def _calc_max_drawdown(equity_values):
    peak = np.maximum.accumulate(equity_values)
    drawdown = (equity_values - peak) / peak
    return float(abs(np.min(drawdown)))


def _validate_metrics(metrics):
    warnings = []
    if metrics["sharpe_ratio"] > 4:
        warnings.append(f"WARNING: Sharpe {metrics['sharpe_ratio']:.2f} > 4, likely look-ahead bias")
    if metrics["win_rate"] < 0.35:
        warnings.append(f"WARNING: Win rate {metrics['win_rate']:.1%} < 35%, unusual distribution")
    if metrics["win_rate"] > 0.85:
        warnings.append(f"WARNING: Win rate {metrics['win_rate']:.1%} > 85%, unusual distribution")
    if metrics["total_trades"] < 30:
        warnings.append(f"WARNING: Only {metrics['total_trades']} trades, sample too small")
    return warnings
