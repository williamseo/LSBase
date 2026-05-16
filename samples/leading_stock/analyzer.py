from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

GRADE_THRESHOLDS = {"A": 75, "B": 60, "C": 45}
GRADE_LABELS = {
    "A": ("강력 주도주", "success"),
    "B": ("주도주 후보", "primary"),
    "C": ("관찰 종목", "warning"),
    "D": ("비해당", "danger"),
}


def _get_grade(score):
    for grade, threshold in GRADE_THRESHOLDS.items():
        if score >= threshold:
            label, color = GRADE_LABELS[grade]
            return grade, label, color
    label, color = GRADE_LABELS["D"]
    return "D", label, color


def calc_rs_score(ohlcv, index_series):
    if ohlcv is None or index_series is None:
        return 0, []

    periods = [("1주", 5), ("1개월", 21), ("3개월", 63)]
    details = []
    total = 0

    for label, days in periods:
        if len(ohlcv) < days + 2 or len(index_series) < days + 2:
            details.append({"기간": label, "비고": "데이터 부족", "점수": 0})
            continue

        stock_ret = (ohlcv["종가"].iloc[-1] / ohlcv["종가"].iloc[-days - 1] - 1) * 100
        idx_ret = (index_series["종가"].iloc[-1] / index_series["종가"].iloc[-days - 1] - 1) * 100
        excess = round(stock_ret - idx_ret, 2)

        if excess > 10:
            pts, level = 10, "매우 강함 (시장+10%↑)"
        elif excess > 5:
            pts, level = 8, "강함 (시장+5%↑)"
        elif excess > 0:
            pts, level = 5, "보통 (시장 대비 양수)"
        else:
            pts, level = 0, "약함 (시장 하회)"

        total += pts
        details.append({
            "기간": label,
            "종목수익률": f"{stock_ret:+.1f}%",
            "시장수익률": f"{idx_ret:+.1f}%",
            "초과수익": f"{excess:+.1f}%",
            "평가": level,
            "점수": pts,
            "만점": 10,
        })

    return total, details


def calc_volume_score(ohlcv):
    if ohlcv is None or len(ohlcv) < 25:
        return 0, []

    vol = ohlcv["거래량"]
    recent_avg = vol.iloc[-5:].mean()
    base_avg = vol.iloc[-25:-5].mean()

    if base_avg == 0:
        return 0, []

    ratio = recent_avg / base_avg

    if ratio >= 2.0:
        pts, level = 20, "폭발적 (2배↑) — 강한 매수 신호"
    elif ratio >= 1.5:
        pts, level = 15, "강함 (1.5배↑)"
    elif ratio >= 1.2:
        pts, level = 10, "보통 (1.2배↑)"
    elif ratio >= 0.8:
        pts, level = 5, "약함 (거의 변화 없음)"
    else:
        pts, level = 0, "거래량 감소 — 주의 필요"

    details = [{
        "최근5일_평균거래량": f"{int(recent_avg):,}주",
        "기준20일_평균거래량": f"{int(base_avg):,}주",
        "비율": f"{ratio:.2f}배",
        "평가": level,
        "점수": pts,
        "만점": 20,
    }]
    return pts, details


def calc_ma_score(ohlcv):
    if ohlcv is None or len(ohlcv) < 120:
        return 0, []

    close = ohlcv["종가"]
    cur = close.iloc[-1]
    ma5 = close.iloc[-5:].mean()
    ma20 = close.iloc[-20:].mean()
    ma60 = close.iloc[-60:].mean()
    ma120 = close.iloc[-120:].mean()

    conditions = [
        ("현재가 > 5일MA", cur > ma5),
        ("5일MA > 20일MA", ma5 > ma20),
        ("20일MA > 60일MA", ma20 > ma60),
        ("60일MA > 120일MA", ma60 > ma120),
    ]

    met = sum(1 for _, c in conditions if c)
    pts = met * 5

    if met == 4:
        alignment = "완전 정배열 — 강한 상승 추세"
    elif met >= 2:
        alignment = f"부분 정배열 ({met}/4 조건 충족)"
    else:
        alignment = "역배열 — 하락 추세"

    details = [{
        "MA값": {"현재가": int(cur), "5일": int(ma5), "20일": int(ma20),
                 "60일": int(ma60), "120일": int(ma120)},
        "조건": [{"이름": name, "충족": bool(ok)} for name, ok in conditions],
        "정배열": alignment,
        "점수": pts,
        "만점": 20,
    }]
    return pts, details


def calc_high_score(ohlcv):
    if ohlcv is None or len(ohlcv) < 2:
        return 0, []

    data_252 = ohlcv.tail(252)
    high_52w = data_252["고가"].max()
    cur = ohlcv["종가"].iloc[-1]
    ratio = cur / high_52w

    if ratio >= 0.95:
        pts, level = 15, "52주 고점 근접(95%↑) — 강한 모멘텀"
    elif ratio >= 0.90:
        pts, level = 10, "52주 고점 10% 이내"
    elif ratio >= 0.80:
        pts, level = 5, "52주 고점 20% 이내"
    else:
        pts, level = 0, "52주 고점 대비 20% 이상 하락"

    details = [{
        "현재가": int(cur),
        "52주_최고가": int(high_52w),
        "고점대비": f"{ratio * 100:.1f}%",
        "평가": level,
        "점수": pts,
        "만점": 15,
    }]
    return pts, details


def calc_institutional_score(trading_df):
    if trading_df is None or len(trading_df) < 5:
        return 0, [{"비고": "수급 데이터 없음", "점수": 0, "만점": 15}]

    recent = trading_df.tail(5)
    inst_net = int(recent["기관순매수"].sum()) if "기관순매수" in recent.columns else 0
    foreign_net = int(recent["외국인순매수"].sum()) if "외국인순매수" in recent.columns else 0

    pts = (8 if inst_net > 0 else 0) + (7 if foreign_net > 0 else 0)

    def fmt_val(v):
        if abs(v) >= 1e8:
            return f"{v/1e8:+.1f}억원"
        return f"{v/1e4:+.1f}만원"

    inst_label = "순매수 ✓" if inst_net > 0 else "순매도 ✗"
    foreign_label = "순매수 ✓" if foreign_net > 0 else "순매도 ✗"

    if pts >= 13:
        assessment = "기관·외국인 동반 매수 — 강한 수급"
    elif pts >= 7:
        assessment = "한쪽만 매수 — 보통 수급"
    else:
        assessment = "기관·외국인 동반 매도 — 약한 수급"

    details = [{
        "기관_5일순매수": fmt_val(inst_net),
        "기관_평가": inst_label,
        "외국인_5일순매수": fmt_val(foreign_net),
        "외국인_평가": foreign_label,
        "종합평가": assessment,
        "점수": pts,
        "만점": 15,
    }]
    return pts, details


def detect_dropout_signals(ohlcv, trading_df, total_score):
    signals = []
    if ohlcv is None or len(ohlcv) < 20:
        return signals

    close = ohlcv["종가"]
    recent5 = ohlcv.tail(5)

    down = recent5[recent5["종가"] < recent5["시가"]]
    up = recent5[recent5["종가"] >= recent5["시가"]]
    if len(down) > 0 and len(up) > 0:
        d_vol = down["거래량"].mean()
        u_vol = up["거래량"].mean()
        if d_vol > u_vol * 1.5:
            signals.append({
                "type": "danger",
                "icon": "📉",
                "제목": "거래량 동반 하락 (분배 신호)",
                "설명": f"최근 5일 하락일 평균 거래량({int(d_vol):,})이 상승일({int(u_vol):,})보다 {d_vol/u_vol:.1f}배 많습니다.",
            })

    if len(ohlcv) >= 20:
        ma20 = close.iloc[-20:].mean()
        cur = close.iloc[-1]
        if cur < ma20:
            signals.append({
                "type": "warning",
                "icon": "⚠️",
                "제목": "20일 이동평균선 하향 이탈",
                "설명": f"현재가 {int(cur):,}원이 20일MA {int(ma20):,}원을 하회. 단기 추세 약화.",
            })

    if len(ohlcv) >= 60:
        peak = ohlcv.tail(60)["고가"].max()
        cur = close.iloc[-1]
        dd = (cur / peak - 1) * 100
        if dd <= -20:
            signals.append({
                "type": "danger",
                "icon": "🔻",
                "제목": f"60일 고점 대비 {abs(dd):.1f}% 하락",
                "설명": f"60일 최고가 {int(peak):,}원 대비 — 주도주 탈락 가능성 높음.",
            })
        elif dd <= -10:
            signals.append({
                "type": "warning",
                "icon": "⚡",
                "제목": f"60일 고점 대비 {abs(dd):.1f}% 하락",
                "설명": f"60일 최고가 {int(peak):,}원 대비 — 주의 필요.",
            })

    if trading_df is not None and len(trading_df) >= 5:
        rt = trading_df.tail(5)
        if "기관순매수" in rt.columns and (rt["기관순매수"] < 0).all():
            signals.append({
                "type": "warning", "icon": "🏛️",
                "제목": "기관 5일 연속 순매도", "설명": "최근 5거래일 기관 순매도 지속.",
            })
        if "외국인순매수" in rt.columns and (rt["외국인순매수"] < 0).all():
            signals.append({
                "type": "warning", "icon": "🌏",
                "제목": "외국인 5일 연속 순매도", "설명": "최근 5거래일 외국인 순매도 지속.",
            })

    if total_score < 45:
        signals.append({
            "type": "danger", "icon": "📊",
            "제목": f"종합 점수 미달 ({total_score}점)",
            "설명": "주도주 최소 기준(60점) 미달.",
        })

    return signals


async def analyze_stock(fetcher, ticker: str, market: str = "KOSPI", name: str = "") -> dict:
    ohlcv = await fetcher.get_stock_ohlcv(ticker, days=120)
    if ohlcv is None or len(ohlcv) < 20:
        return {"ticker": ticker, "error": "데이터 조회 실패", "total_score": 0}

    upcode = "001" if market == "KOSPI" else "301"
    index_series = await fetcher.get_index_series(upcode, days=120)
    trading_df = await fetcher.get_investor_trading(ticker, days=20)

    rs_score, rs_details = calc_rs_score(ohlcv, index_series)
    vol_score, vol_details = calc_volume_score(ohlcv)
    ma_score, ma_details = calc_ma_score(ohlcv)
    high_score, high_details = calc_high_score(ohlcv)
    inst_score, inst_details = calc_institutional_score(trading_df)

    total = rs_score + vol_score + ma_score + high_score + inst_score
    grade, grade_label, grade_color = _get_grade(total)
    dropout_signals = detect_dropout_signals(ohlcv, trading_df, total)

    chart_df = ohlcv.tail(60).copy()
    close = ohlcv["종가"]
    ma5_ser = close.rolling(5).mean()
    ma20_ser = close.rolling(20).mean()

    def safe_list(s):
        return [None if np.isnan(v) else round(float(v), 0) for v in s.tail(60)]

    chart = {
        "dates": [d.strftime("%Y-%m-%d") for d in chart_df.index],
        "open": chart_df["시가"].tolist(),
        "high": chart_df["고가"].tolist(),
        "low": chart_df["저가"].tolist(),
        "close": chart_df["종가"].tolist(),
        "volume": chart_df["거래량"].tolist(),
        "ma5": safe_list(ma5_ser),
        "ma20": safe_list(ma20_ser),
    }

    cur_price = int(ohlcv["종가"].iloc[-1])
    prev_price = int(ohlcv["종가"].iloc[-2]) if len(ohlcv) >= 2 else cur_price
    chg_pct = round((cur_price / prev_price - 1) * 100, 2)

    return {
        "ticker": ticker,
        "name": name,
        "market": market,
        "current_price": cur_price,
        "change_pct": chg_pct,
        "total_score": total,
        "grade": grade,
        "grade_label": grade_label,
        "grade_color": grade_color,
        "is_leader": total >= 60,
        "scores": {
            "rs":   {"label": "상대강도(RS)", "score": rs_score,   "max": 30, "details": rs_details},
            "vol":  {"label": "거래량",       "score": vol_score,  "max": 20, "details": vol_details},
            "ma":   {"label": "이동평균",     "score": ma_score,   "max": 20, "details": ma_details},
            "high": {"label": "52주고점",     "score": high_score, "max": 15, "details": high_details},
            "inst": {"label": "기관/외국인",  "score": inst_score, "max": 15, "details": inst_details},
        },
        "dropout_signals": dropout_signals,
        "chart": chart,
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
