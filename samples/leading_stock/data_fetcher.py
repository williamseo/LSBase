from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

EXCHGUBUN = "K"


class LSDataFetcher:
    def __init__(self, client):
        self._client = client
        self._index_cache: dict[str, pd.DataFrame] = {}

    async def get_index_series(self, upcode: str, days: int = 130) -> pd.DataFrame | None:
        cache_key = f"{upcode}_{days}"
        if cache_key in self._index_cache:
            return self._index_cache[cache_key]
        df = await self._fetch_index_series(upcode, days)
        if df is not None:
            self._index_cache[cache_key] = df
        return df

    async def get_stock_ohlcv(self, ticker: str, days: int = 130) -> pd.DataFrame | None:
        tr = self._client._repo["t1305"]
        now = datetime.now()
        req = tr.build_request({
            "shcode": ticker,
            "dwmcode": "1",
            "date": now.strftime("%Y%m%d"),
            "idx": "0",
            "cnt": str(days),
            "exchgubun": EXCHGUBUN,
        })
        all_items = []
        try:
            async for item in self._client._api.continuous_query(tr.code, req, spec=tr):
                all_items.append(item)
        except Exception as e:
            logger.warning("OHLCV fetch failed (%s): %s", ticker, e)
            return None
        if not all_items:
            return None
        rows = []
        for item in all_items:
            try:
                dt = datetime.strptime(item.get("date", ""), "%Y%m%d")
            except (ValueError, TypeError):
                continue
            rows.append({
                "Date": dt,
                "시가": int(item.get("open", 0)),
                "고가": int(item.get("high", 0)),
                "저가": int(item.get("low", 0)),
                "종가": int(item.get("close", 0)),
                "거래량": int(item.get("volume", 0)),
                "거래대금": int(item.get("value", 0)),
            })
        df = pd.DataFrame(rows)
        df = df.set_index("Date").sort_index()
        return df

    async def _fetch_index_series(self, upcode: str, days: int = 130) -> pd.DataFrame | None:
        tr = self._client._repo["t1514"]
        req = tr.build_request({
            "upcode": upcode,
            "gubun1": " ",
            "gubun2": "1",
            "cts_date": " ",
            "cnt": 1,
            "rate_gbn": "1",
        })
        all_items = []
        try:
            async for item in self._client._api.continuous_query(tr.code, req, spec=tr):
                all_items.append(item)
        except Exception as e:
            logger.warning("Index data fetch failed: %s", e)
            return None
        if not all_items:
            return None
        rows = []
        for item in all_items:
            try:
                dt = datetime.strptime(item.get("date", ""), "%Y%m%d")
            except (ValueError, TypeError):
                continue
            rows.append({
                "Date": dt,
                "종가": float(item.get("jisu", 0)),
                "시가": float(item.get("openjisu", 0)),
                "고가": float(item.get("highjisu", 0)),
                "저가": float(item.get("lowjisu", 0)),
                "거래량": int(item.get("volume", 0)),
                "외인순매수": int(item.get("frgsvolume", 0)),
                "기관순매수": int(item.get("orgsvolume", 0)),
            })
        df = pd.DataFrame(rows)
        df = df.set_index("Date").sort_index()
        return df

    async def get_investor_trading(self, ticker: str, days: int = 20) -> pd.DataFrame | None:
        tr = self._client._repo["t1717"]
        now = datetime.now()
        end_dt = now.strftime("%Y%m%d")
        start_dt = (now - timedelta(days=days * 2)).strftime("%Y%m%d")
        req = tr.build_request({
            "shcode": ticker,
            "gubun": "0",
            "fromdt": start_dt,
            "todt": end_dt,
            "exchgubun": EXCHGUBUN,
        })
        try:
            response = await self._client._api.query(tr.code, req)
            parsed = tr.parse_response(response.body)
        except Exception as e:
            logger.warning("Investor trading fetch failed (%s): %s", ticker, e)
            return None
        data_block = parsed.get("t1717OutBlock1", [])
        if not data_block:
            return None
        rows = []
        for item in data_block:
            try:
                dt = datetime.strptime(item.get("date", ""), "%Y%m%d")
            except (ValueError, TypeError):
                continue
            rows.append({
                "Date": dt,
                "기관순매수": int(item.get("orgsvolume", 0)),
                "외국인순매수": int(item.get("frgsvolume", 0)),
            })
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df = df.set_index("Date").sort_index()
        return df.tail(days)

    async def get_stock_name(self, ticker: str) -> str:
        tr = self._client._repo["t1102"]
        req = tr.build_request({
            "shcode": ticker,
            "exchgubun": EXCHGUBUN,
        })
        try:
            response = await self._client._api.query(tr.code, req)
            parsed = tr.parse_response(response.body)
            data = parsed.get("t1102OutBlock", {})
            return data.get("hname", ticker)
        except Exception as e:
            logger.warning("Stock name fetch failed (%s): %s", ticker, e)
            return ticker


async def rate_limited_scan(fetcher, tickers, analyze_func):
    results = []
    total = len(tickers)
    for i, (ticker, (name, market)) in enumerate(tickers):
        try:
            if i > 0:
                await asyncio.sleep(1.2)
            logger.info("스캔 %d/%d: %s(%s) 분석 시작...", i + 1, total, name, ticker)
            r = await analyze_func(fetcher, ticker, market)
            if "error" not in r:
                results.append(r)
                logger.info("  → %s: %d점 (%s)", name, r["total_score"], r["grade_label"])
            else:
                logger.warning("  → %s: %s", name, r.get("error"))
        except Exception as e:
            logger.warning("Scan %s (%s) failed: %s", name, ticker, e)
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results
