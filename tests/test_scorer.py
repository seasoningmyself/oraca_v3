from market_data.scanners.scorer import (
    breakout20_score,
    grail_score,
    blackreign_score,
    dominion_score,
)


def test_breakout20_full_score():
    score = breakout20_score(
        breakout=0.05,  # 5% above HHV10 (caps at 2%)
        rel_vol=2.0,
        rsi=70,
        macd_hist=0.5,
        bb_pct=0.5,
        atrp=1.0,
        multitf=1,
    )
    assert 90 <= score <= 100


def test_breakout20_zero_breakout():
    score = breakout20_score(
        breakout=0.0,
        rel_vol=2.0,
        rsi=70,
        macd_hist=0.5,
        bb_pct=0.5,
        atrp=1.0,
        multitf=1,
    )
    assert score < 60  # no breakout component


def test_breakout20_high_atr_penalty():
    score_low_atr = breakout20_score(
        breakout=0.02,
        rel_vol=2.0,
        rsi=70,
        macd_hist=0.5,
        bb_pct=0.5,
        atrp=1.0,
        multitf=1,
    )
    score_high_atr = breakout20_score(
        breakout=0.02,
        rel_vol=2.0,
        rsi=70,
        macd_hist=0.5,
        bb_pct=0.5,
        atrp=10.0,
        multitf=1,
    )
    assert score_high_atr < score_low_atr


def test_grail_compression_and_breakout():
    score = grail_score(
        close=102,
        r1=100,
        bb_width=2.0,  # percent
        bb_width_thresh=0.05,
        rel_vol_20=2.0,
        trend_bits=[1, 1, 1, 0],
        macd_hist=0.2,
        macd_hist_prev1=0.1,
        macd_hist_prev2=0.0,
        rsi=50,
        atrp=1.0,
    )
    assert score > 60


def test_grail_no_breakout_no_score():
    score = grail_score(
        close=99,
        r1=100,
        bb_width=2.0,
        bb_width_thresh=0.05,
        rel_vol_20=2.0,
        trend_bits=[1, 1, 1, 1],
        macd_hist=0.2,
        macd_hist_prev1=0.1,
        macd_hist_prev2=0.0,
        rsi=50,
        atrp=1.0,
    )
    assert score < 70  # no breakout; score should drop below the strong-case path


def test_blackreign_strong_pullback_reentry():
    score = blackreign_score(
        trend_macro=True,
        dist20=0.02,
        dist50=0.03,
        rel_vol_20=0.6,
        rsi=45,
        macd_hist=-0.1,
        macd_hist_prev=0.0,
        reentry_flag=True,
        ma_reclaim_flag=True,
        atrp=1.0,
    )
    assert score > 60


def test_blackreign_no_trend_low_score():
    score = blackreign_score(
        trend_macro=False,
        dist20=0.02,
        dist50=0.03,
        rel_vol_20=0.6,
        rsi=45,
        macd_hist=-0.1,
        macd_hist_prev=0.0,
        reentry_flag=True,
        ma_reclaim_flag=True,
        atrp=1.0,
    )
    assert score < 70  # missing trend should reduce score significantly


def test_dominion_meta_score_from_base():
    score = dominion_score(
        base_scores={"breakout20": 90, "grail": 50},
        res_distance=0.15,
        rr=4.0,
        trend_bits=[1, 1, 1, 1],
        atrp=5.0,
    )
    assert score > 80


def test_dominion_penalizes_low_rr():
    high_rr = dominion_score(
        base_scores={"breakout20": 90},
        res_distance=0.15,
        rr=4.0,
        trend_bits=[1, 1, 1, 1],
        atrp=5.0,
    )
    low_rr = dominion_score(
        base_scores={"breakout20": 90},
        res_distance=0.15,
        rr=1.0,
        trend_bits=[1, 1, 1, 1],
        atrp=5.0,
    )
    assert low_rr < high_rr


def test_dominion_penalizes_resistance():
    clear = dominion_score(
        base_scores={"breakout20": 90},
        res_distance=0.2,
        rr=3.0,
        trend_bits=[1, 1, 1, 1],
        atrp=5.0,
    )
    tight = dominion_score(
        base_scores={"breakout20": 90},
        res_distance=0.01,
        rr=3.0,
        trend_bits=[1, 1, 1, 1],
        atrp=5.0,
    )
    assert tight < clear
