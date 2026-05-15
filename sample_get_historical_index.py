import asyncio
from datetime import datetime, timedelta
from lsbase import MarketClient
from lsbase.core.exceptions import APIRequestError


def print_data(title: str, data: list[dict]):
    total_items = len(data)
    if not data:
        print(f"\n{'='*30} {title} (총 0건) {'='*30}")
        print("조회된 데이터가 없습니다.")
        print("=" * 82)
        return

    print(f"\n{'='*30} {title} (총 {total_items}건) {'='*30}")

    headers = data[0].keys()
    header_line = " | ".join(f"{h:<12}" for h in headers)
    print(header_line)
    print("-" * len(header_line))

    items_to_print = data[:5]
    if total_items > 7:
        items_to_print.append(None)
        items_to_print.extend(data[-2:])

    for item in items_to_print:
        if item is None:
            print("...".center(len(header_line)))
            continue
        row_line = " | ".join(f"{str(v):<12}" for v in item.values())
        print(row_line)

    print("=" * len(header_line))


async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        if not await client.connect():
            return

        today = datetime.now()
        five_years_ago = today - timedelta(days=5 * 365)
        start_date_str = five_years_ago.strftime('%Y%m%d')
        end_date_str = today.strftime('%Y%m%d')

        KOSPI_UPCODE = "001"

        # --- 1. t8419 조회 (업종차트, 연속조회) ---
        print(f"\n[t8419] '{KOSPI_UPCODE}' 업종 데이터 조회를 시작합니다.")
        params = client._repo["t8419"].build_request({
            "shcode": KOSPI_UPCODE, "gubun": "3", "qrycnt": 2000,
            "sdate": start_date_str, "edate": end_date_str,
            "cts_date": "", "comp_yn": "N"
        })

        t8419_data = [item async for item in client._api.continuous_query("t8419", params)]

        if t8419_data:
            simplified = [
                {"date": i.get("date"), "open": i.get("open"), "high": i.get("high"),
                 "low": i.get("low"), "close": i.get("close"), "volume": i.get("jdiff_vol")}
                for i in t8419_data
            ]
            print_data("t8419 업종차트 (주별): KOSPI", simplified)

        # --- 2. t1514 조회 (업종기간별추이, 연속조회) ---
        print(f"\n[t1514] '{KOSPI_UPCODE}' 업종 데이터 조회를 시작합니다.")
        params = client._repo["t1514"].build_request({
            "upcode": KOSPI_UPCODE, "gubun1": "1", "gubun2": "2",
            "cts_date": "", "cnt": 500, "rate_gbn": "1"
        })

        t1514_data = [item async for item in client._api.continuous_query("t1514", params)]

        if t1514_data:
            simplified = [
                {"date": i.get("date"), "jisu": i.get("jisu"), "sign": i.get("sign"),
                 "change": i.get("change"), "volume": i.get("volume"),
                 "frgs_vol": i.get("frgsvolume"), "orgs_vol": i.get("orgsvolume")}
                for i in t1514_data
            ]
            filtered = [d for d in simplified if d['date'] >= start_date_str]
            print_data("t1514 업종기간별추이 (주별): KOSPI", filtered)

    except APIRequestError as e:
        print(f"\n❌ API 요청 오류가 발생했습니다: {e}")
    except Exception as e:
        print(f"\n❌ 알 수 없는 오류가 발생했습니다: {e}")
    finally:
        if client and client._open_api and client._open_api.connected:
            print("\nAPI 연결을 종료합니다.")
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
