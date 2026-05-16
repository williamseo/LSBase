from __future__ import annotations

import asyncio
import io
import json
import logging
from datetime import datetime as dt

from flask import Flask, jsonify, render_template, request, send_file

from lsbase import MarketClient

from .analyzer import analyze_stock
from .data_fetcher import LSDataFetcher, rate_limited_scan

logger = logging.getLogger(__name__)


UNIVERSE = {
    "005930": ("삼성전자", "KOSPI"),
    "000660": ("SK하이닉스", "KOSPI"),
    "207940": ("삼성바이오로직스", "KOSPI"),
    "005380": ("현대차", "KOSPI"),
    "000270": ("기아", "KOSPI"),
    "068270": ("셀트리온", "KOSPI"),
    "035420": ("NAVER", "KOSPI"),
    "035720": ("카카오", "KOSPI"),
    "051910": ("LG화학", "KOSPI"),
    "373220": ("LG에너지솔루션", "KOSPI"),
    "105560": ("KB금융", "KOSPI"),
    "055550": ("신한지주", "KOSPI"),
    "066570": ("LG전자", "KOSPI"),
    "028260": ("삼성물산", "KOSPI"),
    "011200": ("HMM", "KOSPI"),
    "003490": ("대한항공", "KOSPI"),
    "034220": ("LG디스플레이", "KOSPI"),
    "036570": ("엔씨소프트", "KOSPI"),
    "352820": ("하이브", "KOSPI"),
    "402340": ("SK스퀘어", "KOSPI"),
    "086520": ("에코프로", "KOSDAQ"),
    "247540": ("에코프로비엠", "KOSDAQ"),
    "196170": ("알테오젠", "KOSDAQ"),
    "263750": ("펄어비스", "KOSDAQ"),
    "293490": ("카카오게임즈", "KOSDAQ"),
    "035900": ("JYP Ent.", "KOSDAQ"),
    "403870": ("HPSP", "KOSDAQ"),
    "112040": ("위메이드", "KOSDAQ"),
}

app = Flask(__name__)

_client: MarketClient | None = None
_fetcher: LSDataFetcher | None = None
_loop: asyncio.AbstractEventLoop | None = None


def _run_async(coro):
    global _loop
    try:
        loop = asyncio.get_running_loop()
        return loop.run_until_complete(asyncio.ensure_future(coro))
    except RuntimeError:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
        return _loop.run_until_complete(coro)


def get_client():
    global _client, _fetcher
    if _client is None:
        _client = MarketClient(monitor_market_state=False, api_call_rate=1.0, api_burst=1)
        ok = _run_async(_client.connect())
        if not ok:
            raise RuntimeError(f"LS증권 API 연결 실패: {_client._open_api.last_message}")
        _fetcher = LSDataFetcher(_client)
        logger.info("MarketClient 연결 완료 (rate=1/s, burst=1)")
    return _client, _fetcher


@app.route("/")
def dashboard():
    return render_template("leading_dashboard.html", universe=sorted(UNIVERSE.items()))


@app.route("/analyze/<ticker>")
def analyze(ticker: str):
    info = UNIVERSE.get(ticker)
    if not info:
        return jsonify({"error": f"Unknown ticker: {ticker}"}), 404
    try:
        _, fetcher = get_client()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    name, market = info
    result = _run_async(analyze_stock(fetcher, ticker, market))
    return jsonify(result)


@app.route("/scan")
def scan():
    limit = int(request.args.get("limit", 0))
    tickers = list(UNIVERSE.items())
    if limit > 0:
        tickers = tickers[:limit]
    try:
        _, fetcher = get_client()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    results = _run_async(rate_limited_scan(fetcher, tickers, analyze_stock))
    return jsonify(results)


@app.route("/report")
def report():
    limit = int(request.args.get("limit", 0))
    tickers = list(UNIVERSE.items())
    if limit > 0:
        tickers = tickers[:limit]
    try:
        _, fetcher = get_client()
    except RuntimeError as e:
        return f"<h2>오류: {e}</h2>", 503

    results = _run_async(rate_limited_scan(fetcher, tickers, analyze_stock))
    rows = []
    for r in results:
        rows.append({
            "ticker": r["ticker"], "name": r["name"], "market": r["market"],
            "price": f"{r['current_price']:,}", "change_pct": r["change_pct"],
            "total_score": r["total_score"], "grade": r["grade"],
            "grade_label": r["grade_label"], "grade_color": r["grade_color"],
            "is_leader": r["is_leader"],
            "signals_count": len(r.get("dropout_signals", [])),
            "rs_score": r["scores"]["rs"]["score"],
            "vol_score": r["scores"]["vol"]["score"],
            "ma_score": r["scores"]["ma"]["score"],
            "high_score": r["scores"]["high"]["score"],
            "inst_score": r["scores"]["inst"]["score"],
        })
    return render_template("leading_report.html", rows=rows, generated_at=dt.now().strftime("%Y-%m-%d %H:%M"))


@app.route("/report/download")
def report_download():
    try:
        _, fetcher = get_client()
    except RuntimeError as e:
        return f"<h2>오류: {e}</h2>", 503
    results = _run_async(rate_limited_scan(fetcher, list(UNIVERSE.items()), analyze_stock))
    rows = []
    for r in results:
        rows.append({
            "ticker": r["ticker"], "name": r["name"], "market": r["market"],
            "price": f"{r['current_price']:,}", "change_pct": r["change_pct"],
            "total_score": r["total_score"], "grade": r["grade"],
            "grade_label": r["grade_label"], "is_leader": r["is_leader"],
            "rs_score": r["scores"]["rs"]["score"],
            "vol_score": r["scores"]["vol"]["score"],
            "ma_score": r["scores"]["ma"]["score"],
            "high_score": r["scores"]["high"]["score"],
            "inst_score": r["scores"]["inst"]["score"],
        })
    html = render_template("leading_report.html", rows=rows)
    buf = io.BytesIO(html.encode("utf-8"))
    fname = f"주도주_리포트_{dt.now().strftime('%Y%m%d_%H%M')}.html"
    return send_file(buf, as_attachment=True, download_name=fname, mimetype="text/html")
