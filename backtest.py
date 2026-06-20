import numpy as np
import pandas as pd
from config import *
from signal_detector import check_signal


class BacktestEngine:
    def __init__(self, tokens, fg_series):
        self.tokens = tokens
        self.fg = fg_series
        self.trades = []
        self.equity = []
        self.capital = STARTING_CAPITAL

    def run(self):
        total_periods = len(self.fg)
        token_names = list(self.tokens.keys())
        self.equity.append({"date": self.fg.index[0], "equity": self.capital})

        positions = {}

        for i in range(SENTIMENT_LOOKBACK, total_periods):
            for tname in token_names:
                tdata = self.tokens[tname]
                is_open = tname in positions

                if not is_open:
                    sig, reason = check_signal(tdata, self.fg, i)
                    if sig:
                        current_exposure = sum(p["pos_frac"] for p in positions.values())
                        if current_exposure + POSITION_SIZE_FRACTION <= MAX_SIMULTANEOUS_POSITIONS * POSITION_SIZE_FRACTION:
                            entry_price = tdata.iloc[i].close
                            positions[tname] = {
                                "token": tname,
                                "entry_idx": i,
                                "entry_date": str(tdata.index[i]),
                                "entry_price": float(entry_price),
                                "entry_fg": float(self.fg.iloc[i]),
                                "pos_frac": POSITION_SIZE_FRACTION,
                                "pos_value": POSITION_SIZE_FRACTION * self.capital,
                                "reason": reason,
                            }
                else:
                    pos = positions[tname]
                    current_price = tdata.iloc[i].close
                    candles_held = i - pos["entry_idx"]
                    pnl_pct_short = (pos["entry_price"] - current_price) / pos["entry_price"]

                    exit_now = False
                    exit_reason = ""

                    if candles_held >= EXIT_HOLD_CANDLES:
                        exit_now = True
                        exit_reason = "max_hold"
                    elif pnl_pct_short >= EXIT_PROFIT_TARGET:
                        exit_now = True
                        exit_reason = "price_target"
                    elif self.fg.iloc[i] < EXIT_FEAR_GREED_FLOOR:
                        exit_now = True
                        exit_reason = "fear_greed_exit"

                    if exit_now:
                        pnl_amount = pnl_pct_short * pos["pos_value"]
                        self.capital += pnl_amount

                        trade = {
                            **pos,
                            "exit_idx": i,
                            "exit_date": str(tdata.index[i]),
                            "exit_price": float(current_price),
                            "exit_fg": float(self.fg.iloc[i]),
                            "pnl_pct": round(pnl_pct_short, 6),
                            "pnl_amount": round(pnl_amount, 2),
                            "exit_reason": exit_reason,
                            "candles_held": candles_held,
                        }
                        self.trades.append(trade)
                        self.equity.append({"date": tdata.index[i], "equity": self.capital})
                        del positions[tname]

                        for p in positions.values():
                            p["pos_value"] = POSITION_SIZE_FRACTION * self.capital

        equity_df = pd.DataFrame(self.equity)
        if not equity_df.empty:
            equity_df.set_index("date", inplace=True)
            equity_df = equity_df.resample("D").last().ffill()
        else:
            equity_df = pd.DataFrame({"equity": [self.capital]}, index=[self.fg.index[0]])

        return self.trades, equity_df
