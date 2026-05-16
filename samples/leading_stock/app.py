from __future__ import annotations

import asyncio
import io
import logging
import threading
import time
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
_loop_thread: threading.Thread | None = None

_scan_cache: dict = {}
SCAN_CACHE_TTL = 300


def _start_loop():
    global _loop, _loop_thread
    if _loop is not None:
        return
    _loop = asyncio.new_event_loop()
    _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
    _loop_thread.start()


def _run_async(coro):
    _start_loop()
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()


def get_client():
    global _client, _fetcher
    if _client is None:
        _start_loop()
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
    try:
        result = _run_async(analyze_stock(fetcher, ticker, market, name))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/scan")
def scan():
    limit = int(request.args.get("limit", 0))
    tickers = list(UNIVERSE.items())
    if limit > 0:
        tickers = tickers[:limit]

    cache_key = f"scan_{limit}_{len(tickers)}"
    cached = _scan_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < SCAN_CACHE_TTL:
        return jsonify(cached["data"])

    try:
        _, fetcher = get_client()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    try:
        results = _run_async(rate_limited_scan(fetcher, tickers, analyze_stock))
        _scan_cache[cache_key] = {"data": results, "ts": time.time()}
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _format_rows(results):
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
    return rows


@app.route("/report")
def report():
    limit = int(request.args.get("limit", 0))
    tickers = list(UNIVERSE.items())
    if limit > 0:
        tickers = tickers[:limit]

    cache_key = f"report_{limit}_{len(tickers)}"
    cached = _scan_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < SCAN_CACHE_TTL:
        return render_template("leading_report.html", rows=_format_rows(cached["data"]),
                               generated_at=dt.now().strftime("%Y-%m-%d %H:%M"))

    try:
        _, fetcher = get_client()
    except RuntimeError as e:
        return f"<h2>오류: {e}</h2>", 503
    try:
        results = _run_async(rate_limited_scan(fetcher, tickers, analyze_stock))
        _scan_cache[cache_key] = {"data": results, "ts": time.time()}
        return render_template("leading_report.html", rows=_format_rows(results),
                               generated_at=dt.now().strftime("%Y-%m-%d %H:%M"))
    except Exception as e:
        return f"<h2>오류: {e}</h2>", 500


@app.route("/report/download")
def report_download():
    cache_key = "report_download"
    cached = _scan_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < SCAN_CACHE_TTL:
        results = cached["data"]
    else:
        try:
            _, fetcher = get_client()
        except RuntimeError as e:
            return f"<h2>오류: {e}</h2>", 503
        try:
            results = _run_async(rate_limited_scan(fetcher, list(UNIVERSE.items()), analyze_stock))
            _scan_cache[cache_key] = {"data": results, "ts": time.time()}
        except Exception as e:
            return f"<h2>오류: {e}</h2>", 500

    rows = _format_rows(results)
    html = render_template("leading_report.html", rows=rows)
    buf = io.BytesIO(html.encode("utf-8"))
    fname = f"주도주_리포트_{dt.now().strftime('%Y%m%d_%H%M')}.html"
    return send_file(buf, as_attachment=True, download_name=fname, mimetype="text/html")
