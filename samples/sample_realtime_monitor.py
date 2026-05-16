import asyncio
from lsbase import MarketClient

STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "207940": "삼성바이오로직스",
    "068270": "셀트리온",
}

def on_execution(sender, trcode, key, data):
    if trcode != "S3_" or key not in STOCKS:
        return
    name = STOCKS[key]
    price = int(data.get("price", 0))
    volume = int(data.get("cvolume", 0))
    sign = data.get("sign", "")
    change = int(data.get("change", 0))
    chetime = data.get("chetime", "")
    time_str = f"{chetime[:2]}:{chetime[2:4]}:{chetime[4:]}" if len(chetime) >= 6 else chetime
    sign_char = "▲" if sign == "2" else "▼" if sign == "5" else " "
    print(f"[{time_str}] {name:14s} {sign_char} {price:>8,}원 ({change:+,}원)  체결량={volume:>6,}주")

async def main():
    client = MarketClient(monitor_market_state=False)
    try:
        client._open_api.on_realtime.connect(on_execution)
        if not await client.connect():
            return
        print(f"=== 실시간 체결 모니터링 ({len(STOCKS)}개 종목) ===")
        print(f"{'시간':<10s} {'종목명':<14s} {'   현재가':>10s} {'변동':>10s} {'체결량':>10s}")
        print("-" * 56)
        for code in STOCKS:
            await client._open_api.add_realtime("S3_", code)
        print("\nCtrl+C로 종료")
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        if client._open_api and client._open_api.connected:
            for code in STOCKS:
                await client._open_api.remove_realtime("S3_", code)
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
