"""
Scoring utilities for scanners.
"""
from __future__ import annotations
from typing import Optional


def breakout20_score(
    breakout: float,
    rel_vol: float,
    rsi: float,
    macd_hist: float,
    bb_pct: Optional[float],
    atrp: Optional[float],
    multitf: int,
) -> float:
    """
    Compute breakout20_v1 score (0-100) using weighted components.
    Weights: breakout=40, volume=25, momentum=20, mtf=10, risk=5.
    """
    breakout_score = min(breakout / 0.02, 1) * 40 if breakout else 0
    volume_score = min(max(rel_vol - 1, 0) / 1.0, 1) * 25 if rel_vol is not None else 0
    momentum_bits = []
    if rsi is not None:
        momentum_bits.append(min(max((rsi - 50) / 35, 0), 1))
    momentum_bits.append(1 if macd_hist and macd_hist > 0 else 0)
    if bb_pct is not None:
        momentum_bits.append(1 if 0.3 <= bb_pct <= 0.8 else 0)
    momentum_score = (sum(momentum_bits) / len(momentum_bits) if momentum_bits else 0) * 20
    mtf_score = (1 if multitf else 0) * 10
    risk_score = (1 - min((atrp or 0) / 5, 1)) * 5 if atrp is not None else 0
    return breakout_score + volume_score + momentum_score + mtf_score + risk_score


def grail_score(
    *,
    close: float,
    r1: Optional[float],
    bb_width: Optional[float],
    bb_width_thresh: float,
    rel_vol_20: Optional[float],
    trend_bits: list,
    macd_hist: Optional[float],
    macd_hist_prev1: Optional[float],
    macd_hist_prev2: Optional[float],
    rsi: Optional[float],
    atrp: Optional[float],
    breakout_clearance_cap: float = 0.02,
) -> float:
    # Weights
    W_comp = 20
    W_breakout = 20
    W_volume = 20
    W_mtf = 20
    W_coil = 10
    W_risk = 10

    # Compression: smaller bb_width is better, capped at threshold
    if bb_width is None or bb_width_thresh <= 0:
        F_comp = 0
    else:
        F_comp = 1 - min(bb_width / (bb_width_thresh * 100), 1)  # bb_width is already percent

    # Breakout clearance above R1
    if r1:
        clearance = close / r1 - 1
        F_breakout = min(clearance / breakout_clearance_cap, 1)
    else:
        F_breakout = 0

    # Volume expansion
    F_volume = min(max((rel_vol_20 or 0) - 1.0, 0) / 1.0, 1)

    # MTF trend bits
    F_mtf = (sum(trend_bits) / len(trend_bits)) if trend_bits else 0

    # Coil quality
    coil_bits = [
        1 if (macd_hist is not None and macd_hist_prev1 is not None and macd_hist_prev2 is not None and macd_hist > macd_hist_prev1 > macd_hist_prev2) else 0,
        1 if (rsi is not None and 45 <= rsi <= 60) else 0,
    ]
    F_coil = sum(coil_bits) / len(coil_bits)

    # Risk (ATR% lower is better)
    F_risk = 1 - min((atrp or 0) / 5.0, 1)

    return (
        W_comp * F_comp +
        W_breakout * F_breakout +
        W_volume * F_volume +
        W_mtf * F_mtf +
        W_coil * F_coil +
        W_risk * F_risk
    )


def blackreign_score(
    *,
    trend_macro: bool,
    dist20: float,
    dist50: float,
    rel_vol_20: Optional[float],
    rsi: Optional[float],
    macd_hist: Optional[float],
    macd_hist_prev: Optional[float],
    reentry_flag: bool,
    ma_reclaim_flag: bool,
    atrp: Optional[float],
) -> float:
    # Weights
    W_trend = 20
    W_pullback = 25
    W_vol_quiet = 15
    W_mom_reset = 15
    W_reentry = 15
    W_risk = 10

    # Trend
    F_trend = 1 if trend_macro else 0

    # Pullback quality (near SMA20/50)
    nearest_abs = min(abs(dist20), abs(dist50))
    F_pullback = 1 - min(nearest_abs / 0.05, 1)  # 5% offset -> 0

    # Volume quietness (ideal rel_vol <=0.5, bad at >=1.0)
    rv = rel_vol_20 or 0
    F_vol_quiet = 1 - min(max(rv - 0.5, 0) / 0.5, 1)

    # Momentum reset
    mom_bits = [
        1 if (rsi is not None and 35 <= rsi <= 55) else 0,
        1 if (macd_hist is not None and macd_hist_prev is not None and macd_hist < macd_hist_prev) else 0,
    ]
    F_mom_reset = sum(mom_bits) / len(mom_bits)

    # Re-entry trigger
    re_bits = [
        1 if reentry_flag else 0,
        1 if ma_reclaim_flag else 0,
    ]
    F_reentry = sum(re_bits) / len(re_bits)

    # Risk
    F_risk = 1 - min((atrp or 0) / 5.0, 1)

    return (
        W_trend * F_trend +
        W_pullback * F_pullback +
        W_vol_quiet * F_vol_quiet +
        W_mom_reset * F_mom_reset +
        W_reentry * F_reentry +
        W_risk * F_risk
    )


def dominion_score(
    *,
    base_scores: Dict[str, float],
    res_distance: Optional[float],
    rr: Optional[float],
    trend_bits: list,
    atrp: Optional[float],
) -> float:
    """
    Meta-score on top of base detectors (breakout20/grail/blackreign).
    base_scores: dict of detector -> score (0-100)
    res_distance: (NEAR_RES - close)/close
    rr: (TARGET - close)/(close - SUPPORT)
    trend_bits: [Trend_D, Trend_H4, Trend_H1, Trend_M15] as 0/1
    atrp: ATR% of price
    """
    W_base = 40
    W_res = 20
    W_rr = 15
    W_mtf_dom = 15
    W_vol_dom = 10

    F_base = max(base_scores.values()) / 100 if base_scores else 0
    F_res = min(max((res_distance or 0) / 0.10, 0), 1)
    F_rr = min((rr or 0) / 3.0, 1)
    F_mtf_dom = (sum(trend_bits) / len(trend_bits)) if trend_bits else 0

    if atrp is None:
        F_vol_dom = 0
    elif atrp <= 2:
        F_vol_dom = atrp / 2.0
    elif atrp >= 10:
        F_vol_dom = max(1 - (atrp - 10) / 10.0, 0)
    else:
        F_vol_dom = 1.0

    return (
        W_base * F_base +
        W_res * F_res +
        W_rr * F_rr +
        W_mtf_dom * F_mtf_dom +
        W_vol_dom * F_vol_dom
    )
