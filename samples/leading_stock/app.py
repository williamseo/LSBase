from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import time

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

from lsbase import MarketClient

from .analyzer import analyze_stock
from .data_fetcher import LSDataFetcher

logger = logging.getLogger(__name__)


class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


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


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(asyncio.ensure_future(coro))


@app.route("/")
def dashboard():
    return render_template("leading_dashboard.html", universe=sorted(UNIVERSE.items()))


@app.route("/analyze/<ticker>")
def analyze(ticker: str):
    info = UNIVERSE.get(ticker)
    if not info:
        return jsonify({"error": f"Unknown ticker: {ticker}"}), 404
    name, market = info

    async def _run():
        client = MarketClient(monitor_market_state=False)
        try:
            if not await client.connect():
                return {"error": "LS증권 API 연결 실패"}
            fetcher = LSDataFetcher(client)
            result = await analyze_stock(fetcher, ticker, market)
            return result
        finally:
            await client.disconnect()

    result = _run_async(_run())
    return jsonify(result)


@app.route("/scan")
def scan():
    limit = int(request.args.get("limit", 0))
    tickers = list(UNIVERSE.items())
    if limit > 0:
        tickers = tickers[:limit]

    async def _run():
        client = MarketClient(monitor_market_state=False)
        try:
            if not await client.connect():
                return {"error": "LS증권 API 연결 실패"}
            fetcher = LSDataFetcher(client)
            results = []
            total = len(tickers)
            for i, (ticker, (name, market)) in enumerate(tickers):
                try:
                    r = await analyze_stock(fetcher, ticker, market)
                    if "error" not in r:
                        results.append(r)
                except Exception as e:
                    logger.warning("Scan %s failed: %s", ticker, e)
                if i % 5 == 0:
                    logger.info("Scan progress: %d/%d", i + 1, total)
            results.sort(key=lambda x: x["total_score"], reverse=True)
            return results
        finally:
            await client.disconnect()

    results = _run_async(_run())
    if isinstance(results, dict) and "error" in results:
        return jsonify(results), 503
    return jsonify(results)


@app.route("/report")
def report():
    limit = int(request.args.get("limit", 0))

    async def _run():
        client = MarketClient(monitor_market_state=False)
        try:
            if not await client.connect():
                return {"error": "LS증권 API 연결 실패"}
            fetcher = LSDataFetcher(client)
            results = []
            tickers = list(UNIVERSE.items())
            if limit > 0:
                tickers = tickers[:limit]
            for ticker, (name, market) in tickers:
                try:
                    r = await analyze_stock(fetcher, ticker, market)
                    if "error" not in r:
                        results.append(r)
                except Exception as e:
                    logger.warning("Report %s failed: %s", ticker, e)
            results.sort(key=lambda x: x["total_score"], reverse=True)
            return results
        finally:
            await client.disconnect()

    results = _run_async(_run())
    if isinstance(results, dict) and "error" in results:
        return f"<h2>오류: {results['error']}</h2>", 503

    rows = []
    for r in results:
        rows.append({
            "ticker": r["ticker"],
            "name": r["name"],
            "market": r["market"],
            "price": f"{r['current_price']:,}",
            "change_pct": r["change_pct"],
            "total_score": r["total_score"],
            "grade": r["grade"],
            "grade_label": r["grade_label"],
            "grade_color": r["grade_color"],
            "is_leader": r["is_leader"],
            "signals_count": len(r.get("dropout_signals", [])),
            "rs_score": r["scores"]["rs"]["score"],
            "vol_score": r["scores"]["vol"]["score"],
            "ma_score": r["scores"]["ma"]["score"],
            "high_score": r["scores"]["high"]["score"],
            "inst_score": r["scores"]["inst"]["score"],
        })

    from datetime import datetime as dt
    return render_template("leading_report.html", rows=rows, generated_at=dt.now().strftime("%Y-%m-%d %H:%M"))


@app.route("/report/download")
def report_download():
    async def _run():
        client = MarketClient(monitor_market_state=False)
        try:
            if not await client.connect():
                return None
            fetcher = LSDataFetcher(client)
            results = []
            for ticker, (name, market) in UNIVERSE.items():
                try:
                    r = await analyze_stock(fetcher, ticker, market)
                    if "error" not in r:
                        results.append(r)
                except Exception:
                    pass
            results.sort(key=lambda x: x["total_score"], reverse=True)
            return results
        finally:
            await client.disconnect()

    results = _run_async(_run())
    if not results:
        return "Scan failed", 503

    rows = []
    for r in results:
        rows.append({
            "ticker": r["ticker"],
            "name": r["name"],
            "market": r["market"],
            "price": f"{r['current_price']:,}",
            "change_pct": r["change_pct"],
            "total_score": r["total_score"],
            "grade": r["grade"],
            "grade_label": r["grade_label"],
            "is_leader": r["is_leader"],
            "rs_score": r["scores"]["rs"]["score"],
            "vol_score": r["scores"]["vol"]["score"],
            "ma_score": r["scores"]["ma"]["score"],
            "high_score": r["scores"]["high"]["score"],
            "inst_score": r["scores"]["inst"]["score"],
        })

    from datetime import datetime as dt
    html = render_template("leading_report.html", rows=rows)
    buf = io.BytesIO(html.encode("utf-8"))
    fname = f"주도주_리포트_{dt.now().strftime('%Y%m%d_%H%M')}.html"
    return send_file(buf, as_attachment=True, download_name=fname, mimetype="text/html")
