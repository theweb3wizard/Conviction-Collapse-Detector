import numpy as np
import pandas as pd
from config import *


def compute_metrics(data, i, lookback=1):
    if i < lookback:
        return None
    prev = data.iloc[i - lookback]
    curr = data.iloc[i]
    price_change = (curr.close - prev.close) / prev.close
    volume_change = (curr.volume - prev.volume) / prev.volume if prev.volume > 0 else 0
    return {"price_change": price_change, "volume_change": volume_change}


def sentiment_decay_estimated(fg_series, i, lookback=SENTIMENT_LOOKBACK, fg_offset=0.0):
    if i < lookback:
        return False
    recent = (fg_series + fg_offset).iloc[i - lookback:i + 1].values
    fg_drop = (recent[-1] - recent[0]) / max(recent[0], 1)

    returns = np.diff(recent) / np.maximum(np.abs(recent[:-1]), 1)
    fg_volatility = np.std(returns)

    decay_proxy = (-fg_drop) + fg_volatility
    threshold = 0.15

    return decay_proxy > threshold


def volume_declining_or_flat(token_data, i, lookback=SENTIMENT_LOOKBACK):
    if i < lookback:
        return False
    recent_vol = token_data.iloc[i - lookback:i + 1].volume.values
    vol_change = (recent_vol[-1] - recent_vol[0]) / max(recent_vol[0], 1)
    return vol_change <= VOLUME_DECLINING_THRESHOLD


def price_momentum_bullish_or_flat(token_data, i, lookback=1):
    m = compute_metrics(token_data, i, lookback)
    if m is None:
        return False
    pc = m["price_change"]
    return (0 <= pc <= PRICE_MOMENTUM_MAX) or (PRICE_FLAT_MIN <= pc <= PRICE_FLAT_MAX)


def fear_greed_extreme(fg_series, i):
    return fg_series.iloc[i] >= FEAR_GREED_THRESHOLD


def check_signal(token_data, fg_series, i, fg_offset=0.0):
    cond4 = fear_greed_extreme(fg_series + fg_offset, i)
    if not cond4:
        return (False, "F&G < 65")

    cond2 = price_momentum_bullish_or_flat(token_data, i)
    if not cond2:
        return (False, "price not flat/bullish")

    cond1 = sentiment_decay_estimated(fg_series, i, fg_offset=fg_offset)
    if not cond1:
        return (False, "no sentiment decay")

    cond3 = volume_declining_or_flat(token_data, i)
    if not cond3:
        return (False, "volume spiking")

    return (True, "CONVICTION_COLLAPSE_DETECTED")


def cmc_skill_function(token_ohlcv, fear_greed_value, lookback_hours=4):
    lookback_bars = lookback_hours // CANDLE_INTERVAL_HOURS
    last_idx = len(token_ohlcv) - 1
    fg_series = pd.Series([fear_greed_value] * len(token_ohlcv), index=token_ohlcv.index)

    if last_idx < max(lookback_bars, SENTIMENT_LOOKBACK):
        return None

    sig, reason = check_signal(token_ohlcv, fg_series, last_idx)
    return {
        "signal": "CONVICTION_COLLAPSE_DETECTED" if sig else "NO_SIGNAL",
        "reason": reason,
        "entry_price": float(token_ohlcv.iloc[last_idx].close),
        "fear_greed": float(fg_series.iloc[last_idx]),
        "timestamp": str(token_ohlcv.index[last_idx]),
    }
