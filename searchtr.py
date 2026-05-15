import sys
from lsbase.core.spec_models import SpecRepository


def main():
    repo = SpecRepository(lazy=False)

    if len(sys.argv) < 2:
        print("사용법: python searchtr.py <TR코드1> [TR코드2 ...]")
        print("   또는: python searchtr.py --search <검색어>")
        sys.exit(1)

    if sys.argv[1] == "--search":
        query = " ".join(sys.argv[2:])
        results = repo.search(query)
        if not results:
            print(f"😭 '{query}' 검색 결과가 없습니다.")
            sys.exit(1)
        print(f"🔍 '{query}' 검색 결과 (총 {len(results)}건):")
        print("-" * 60)
        for spec in results:
            print(f"  [{spec.code:12s}] {spec.name}  ({spec.tr_class.value}, {spec.market.value})")
        sys.exit(0)

    for tr_code in sys.argv[1:]:
        spec = repo.get(tr_code.strip())
        if not spec:
            print(f"😭 TR '{tr_code}'을(를) 찾을 수 없습니다.")
            continue

        print(f"✅ [{spec.code}] {spec.name}")
        print(f"   분류: {spec.tr_class.value}, 시장: {spec.market.value}")
        print(f"   카테고리: {spec.category} > {spec.group}")

        if spec.request_blocks:
            print(f"\n  [요청 블록]")
            for block in spec.request_blocks:
                print(f"    {block.name}:")
                for f in block.fields:
                    req = "필수" if f.is_required else "선택"
                    print(f"      {f.name:20s} {f.korean_name:15s} ({f.python_type.__name__:5s}) [{req}]")

        if spec.response_blocks:
            print(f"\n  [응답 블록]")
            for block in spec.response_blocks:
                print(f"    {block.name}:{' (리스트)' if block.is_repeating else ''}")
                for f in block.fields[:10]:
                    print(f"      {f.name:20s} {f.korean_name:15s} ({f.python_type.__name__:5s})")
                if len(block.fields) > 10:
                    print(f"      ... 외 {len(block.fields) - 10}개 필드")

        if spec.continuation:
            c = spec.continuation
            print(f"\n  [연속조회]")
            print(f"    데이터블록: {c.data_block}")
            print(f"    연속키블록: {c.continuation_block}")
            print(f"    연속키필드: {c.key_fields}")

        print("=" * 60)


if __name__ == "__main__":
    main()
