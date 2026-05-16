"""실제 API 응답과 TR 명세 간 차이 분석 도구.

사용법:
  python tools/validate_spec.py t1102          # 단일 TR 검증
  python tools/validate_spec.py --all          # 전체 TR 검증
  python tools/validate_spec.py --strict t1102 # strict 모드 build_request 테스트
"""
import asyncio
import json
import sys
from lsbase import MarketClient
from lsbase.core.spec_models import SpecRepository, TrSpec


async def validate_one(repo: SpecRepository, code: str, api):
    tr = repo[code]
    if not tr.request_blocks or not tr.request_blocks[0].fields:
        return

    block = tr.request_blocks[0]
    sample_values = {}
    for f in block.fields:
        sample_values[f.name] = "" if f.python_type == str else 0

    try:
        packet = tr.build_request(sample_values, strict=True)
    except (ValueError, TypeError) as e:
        return

    if not api:
        return

    try:
        response = await api.query(tr.code, packet)
        parsed, meta = tr._parse_response_with_meta(response.body)

        issues = []
        if meta["unknown_fields"]:
            issues.append(f"  unknown: {meta['unknown_fields'][:5]}")
        if meta["missing_blocks"]:
            issues.append(f"  missing blocks: {meta['missing_blocks']}")

        if issues:
            print(f"⚠️  [{code}] {tr.name}")
            for i in issues:
                print(i)
        else:
            pass
    except Exception:
        pass


async def main():
    repo = SpecRepository(lazy=False)

    if "--strict" in sys.argv:
        idx = sys.argv.index("--strict")
        codes = sys.argv[idx + 1:]
        for code in codes:
            tr = repo[code]
            if not tr.request_blocks:
                continue
            block = tr.request_blocks[0]
            print(f"\n=== [{code}] {tr.name} (strict 모드) ===")
            print(f"요청블록: {block.name}")
            for f in block.fields:
                print(f"  {f.name:20s} {f.korean_name:15s} ({f.python_type.__name__:5s}) "
                      f"len={f.length or '-':4s} 필수={f.is_required}")
            try:
                packet = tr.build_request(
                    {f.name: "" if f.python_type == str else 0 for f in block.fields},
                    strict=True,
                )
                print(f"  ✅ strict 통과 — {packet}")
            except (ValueError, TypeError) as e:
                print(f"  ❌ {e}")
        return

    codes = sys.argv[1:]
    if not codes or codes[0] == "--all":
        codes = [code for code, raw in repo._load().items()
                 if raw.get("c") != "realtime"][:20]
        print(f"전체 TR 스캔 (처음 20개):")
    else:
        print(f"지정 TR 검증:")

    client = MarketClient(monitor_market_state=False)
    connected = await client.connect()
    api = client._api if connected else None

    for code in codes:
        await validate_one(repo, code, api)

    if connected:
        await client.disconnect()

    print("\n완료.")


if __name__ == "__main__":
    asyncio.run(main())
