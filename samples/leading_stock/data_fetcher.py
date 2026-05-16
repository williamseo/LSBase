from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


class LSDataFetcher:
    """LSBase MarketClient를 통해 데이터를 수집하는 어댑터.

    LeadingStock 분석 엔진에 pandas DataFrame 형태로 데이터를 공급한다.
    """

    def __init__(self, client):
        self._client = client

    async def get_stock_ohlcv(self, ticker: str, days: int = 130) -> pd.DataFrame | None:
        prices = await self._client.stock.get_historical_data(ticker, "day", count=days)
        if not prices:
            return None
        rows = []
        for p in prices:
            rows.append({
                "Date": datetime.strptime(p.date, "%Y%m%d"),
                "시가": p.open,
                "고가": p.high,
                "저가": p.low,
                "종가": p.close,
                "거래량": p.volume,
                "거래대금": p.value,
            })
        df = pd.DataFrame(rows)
        df = df.set_index("Date").sort_index()
        return df

    async def get_index_series(self, upcode: str, days: int = 130) -> pd.DataFrame | None:
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
        try:
            quote = await self._client.stock.get_quote(ticker)
            return quote.symbol_name
        except Exception:
            return ticker
