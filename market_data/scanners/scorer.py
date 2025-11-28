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
