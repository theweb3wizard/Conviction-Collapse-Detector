import numpy as np
import pandas as pd
from datetime import timedelta
from config import *

rng = np.random.default_rng(SEED)


def _make_timestamps(start, periods, hours):
    base = pd.Timestamp(start)
    return [base + timedelta(hours=i * hours) for i in range(periods)]


def generate_fear_greed():
    periods = int((pd.Timestamp(BACKTEST_END) - pd.Timestamp(BACKTEST_START)).total_seconds() // (3600 * CANDLE_INTERVAL_HOURS)) + 1
    fg = np.zeros(periods)

    time_idx = np.arange(periods)
    cycle_a = np.sin(2 * np.pi * time_idx / 1200) * 18
    cycle_b = np.sin(2 * np.pi * time_idx / 360) * 8
    baseline = 50 + cycle_a + cycle_b

    for i in range(periods):
        if i == 0:
            fg[i] = np.clip(baseline[i] + rng.normal(0, 8), FEAR_GREED_MIN, FEAR_GREED_MAX)
        else:
            noise = rng.normal(0, 3)
            fg[i] = np.clip(baseline[i] + 0.4 * (fg[i - 1] - baseline[i - 1]) + noise, FEAR_GREED_MIN, FEAR_GREED_MAX)

    ts = _make_timestamps(BACKTEST_START, periods, CANDLE_INTERVAL_HOURS)
    return pd.Series(fg, index=ts, name="fear_greed")


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _simulate_token(name, periods, fg):
    hype_mu = 30.0
    hype = np.full(periods, hype_mu + rng.normal(0, 10))
    hype[0] = np.clip(hype[0], 5, 95)

    prices = np.full(periods, rng.uniform(*INITIAL_PRICE_RANGE))
    volumes = np.full(periods, VOLUME_BASE * rng.uniform(0.5, 2.0))
    highs = np.zeros(periods)
    lows = np.zeros(periods)
    opens = np.zeros(periods)

    in_pump = False
    pump_hype_target = 0.0

    for i in range(1, periods):
        pump_chance = 0.015 * (1.5 if fg.iloc[i] > 60 else 1.0)

        if not in_pump and rng.random() < pump_chance:
            in_pump = True
            pump_hype_target = rng.uniform(70, 95)
            hype[i] = pump_hype_target * rng.uniform(0.8, 1.0)
        elif in_pump:
            hype[i] = hype[i - 1] * rng.uniform(0.92, 1.0)

            decay_strength = max(0, (hype[i - 1] - hype_mu) / 60.0)
            hype[i] = hype[i - 1] * (1 - 0.04 * decay_strength) + hype_mu * 0.04 * decay_strength
            hype[i] += rng.normal(0, 2)

            if hype[i] < 40 and i > 4:
                in_pump = False
        else:
            reversion = (hype_mu - hype[i - 1]) * 0.01
            hype[i] = hype[i - 1] + reversion + rng.normal(0, 3)

        hype[i] = np.clip(hype[i], 5, 95)

    for i in range(1, periods):
        lag = min(6, i)
        if i - lag - 1 >= 0:
            hype_change = hype[i - lag] - hype[i - lag - 1]
        elif i - lag >= 0:
            hype_change = hype[i - lag] - hype_mu
        else:
            hype_change = 0

        price_impact = hype_change / 100.0 * 0.7
        noise = rng.normal(0, BASE_VOLATILITY * 0.3)
        prices[i] = prices[i - 1] * (1 + price_impact + noise)
        prices[i] = max(prices[i], prices[i - 1] * 0.90)

        vol_ret = rng.normal(0, VOLUME_VOLATILITY * 0.3)
        hype_delta = hype[i] - hype[i - 1]
        vol_from_hype = hype_delta / 100.0 * 2.0
        volumes[i] = volumes[i - 1] * (1 + vol_ret + vol_from_hype)
        volumes[i] = max(volumes[i], VOLUME_BASE * 0.05)

        opens[i] = prices[i - 1]
        highs[i] = max(prices[i], opens[i]) * (1 + rng.uniform(0, 0.02))
        lows[i] = min(prices[i], opens[i]) * (1 - rng.uniform(0, 0.02))

    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": prices, "volume": volumes,
        "hype": hype,
    }, index=_make_timestamps(BACKTEST_START, periods, CANDLE_INTERVAL_HOURS))
    return df


def load_all_data():
    periods = int((pd.Timestamp(BACKTEST_END) - pd.Timestamp(BACKTEST_START)).total_seconds() // (3600 * CANDLE_INTERVAL_HOURS)) + 1
    fg = generate_fear_greed()
    tokens = {}
    for name in TOKEN_NAMES[:NUM_TOKENS]:
        tokens[name] = _simulate_token(name, periods, fg)
    return tokens, fg
