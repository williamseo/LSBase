# lsbase/tools/generate_specs.py
"""
ls_openapi_specs.json → lsbase/_tr_specs.py 생성.

사용법:
    python lsbase/tools/generate_specs.py

출력: lsbase/_tr_specs.py (Python dict literal, ~500KB)
"""

import json
import os
import re
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SPECS_PATH = os.path.join(SCRIPT_DIR, "ls_openapi_specs.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "_tr_specs.py")

# ── 타입 코드 매핑 ──
TYPE_CODE_MAP = {
    "A0001": "str",
    "A0003": "int",
    "A0004": "int",
    "A0005": "float",
    "A0006": "float",
    "A0007": "int",
    "A0008": "str",
}

# ── 시장 매핑 ──
CATEGORY_TO_MARKET = {
    "OAuth 인증": "auth",
    "업종": "sector",
    "주식": "stock",
    "선물/옵션": "futures_options",
    "해외선물": "overseas_futures",
    "해외주식": "overseas_stock",
    "기타": "etc",
    "실시간 시세 투자정보": "etc",
}


def infer_type(type_code: str, length: str | None) -> str:
    """LS 타입 코드 + 길이 → Python 타입 문자열"""
    if length and "." in length:
        return "float"
    return TYPE_CODE_MAP.get(type_code, "str")


def classify_tr(code: str, res_body: list, category: str, req_example: dict) -> str:
    """TR 코드 + 응답 명세 + 카테고리 → TrClass 결정"""
    if not code:
        return "query"
    # OAuth 인증 TR
    if category == "OAuth 인증":
        return "query"
    # 해외/선물 REST TR (o*, g* 접두사)
    if code.startswith(("o", "g")):
        if req_example:
            return "query"
        return "realtime"
    # 실시간: t나 C로 시작하지 않음 (token/revoke/o/g 제외)
    if not code.startswith("t") and not code.startswith("C"):
        return "realtime"
    # 연속조회: 응답에 cts_, idx, cont/contkey 중 하나라도 있음
    res_names = {p.get("name", "") for p in res_body}
    cont_indicators = {n for n in res_names if n.startswith("cts_") or n in ("idx", "cont", "contkey", "cont_key")}
    if cont_indicators:
        return "continuous"
    return "query"


def detect_continuation(code: str, req_body: list, res_body: list, ex_response: dict) -> dict | None:
    """연속조회 TR의 ContinuationSpec 생성"""
    req_field_names = {p.get("name", "") for p in req_body if "InBlock" not in p.get("name", "") and "OutBlock" not in p.get("name", "")}
    res_field_names = {p.get("name", "") for p in res_body if "InBlock" not in p.get("name", "") and "OutBlock" not in p.get("name", "")}

    # 요청/응답 공통 필드 중 연속키 후보
    common = req_field_names & res_field_names
    key_fields = sorted(
        f for f in common
        if f.startswith("cts_") or f in ("cont", "contkey", "cont_key", "idx")
    )
    if not key_fields:
        return None

    # OutBlock1 (데이터) / OutBlock (연속키) 찾기
    data_block = None
    cont_block = None
    for p in res_body:
        name = p.get("name", "")
        if name.endswith("OutBlock1") or name.endswith("OutBlock1"):
            data_block = name
        elif "OutBlock" in name and not name.endswith("1"):
            cont_block = name

    if not data_block or not cont_block:
        return None

    # 종료 조건
    stop = "zero_idx" if "idx" in key_fields else "empty_value"

    return {
        "data_block": data_block,
        "continuation_block": cont_block,
        "key_fields": key_fields,
        "stop_condition": stop,
    }


def parse_blocks(field_list: list, block_keyword: str, is_response: bool) -> list:
    """
    flat한 field_list를 블록 단위로 파싱.

    예: request_body = [
            {"name": "t1102InBlock", ...},   ← 블록 선언
            {"name": "shcode", ...},          ← 블록 내 필드
            {"name": "hname", ...},           ← 블록 내 필드
         ]
    → [{"name": "t1102InBlock", "fields": [shcode, hname], "is_repeating": False}]

    Response의 경우 OutBlock1(리스트)과 OutBlock(dict) 구분.
    """
    blocks = []
    current_block = None

    for p in field_list:
        name = p.get("name", "")
        if block_keyword in name:
            # 새 블록 시작
            if current_block:
                blocks.append(current_block)
            is_repeating = False
            if is_response and name.endswith("1"):
                is_repeating = True
            current_block = {
                "name": name,
                "is_repeating": is_repeating,
                "fields": [],
            }
        else:
            if current_block is None:
                # 블록명 없이 필드만 있는 경우 → 임시 블록
                # 이미지 인증 등 일부 TR
                current_block = {
                    "name": f"{block_keyword}",
                    "is_repeating": False,
                    "fields": [],
                }
            field_spec = {
                "n": name,
                "k": p.get("korean_name") or "",
                "t": infer_type(p.get("type") or "A0001", p.get("length") or ""),
                "l": p.get("length") or "",
                "r": (p.get("required") or "N") == "Y",
            }
            current_block["fields"].append(field_spec)

    if current_block:
        blocks.append(current_block)

    return blocks


def to_pascal_case(name: str) -> str:
    if not isinstance(name, str) or not name:
        return "Unnamed"
    name = re.sub(r"[^a-zA-Z0-9]", "", name)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    return "".join(word.capitalize() for word in s2.split("_"))


def fmt_bool(v: bool) -> str:
    return "True" if v else "False"


def main():
    print(f"Specs 파일 읽는 중: {SPECS_PATH}")
    with open(SPECS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"전체 TR: {sum(len(grp.get('tr_list',[])) for cat in data for grp in cat.get('api_groups',[]))}개")
    print(f"Python 파일 생성 중: {OUTPUT_PATH}")

    lines = []
    lines.append("# -*- coding: utf-8 -*-")
    lines.append("# 이 파일은 lsbase/tools/generate_specs.py에 의해 자동 생성되었습니다.")
    lines.append("# 수동으로 수정하지 마세요. 업데이트: python lsbase/tools/generate_specs.py")
    lines.append("")
    lines.append("SPECS: dict = {")
    lines.append("")

    count = 0
    for cat in data:
        category = cat.get("category", "")
        for grp in cat.get("api_groups", []):
            group = grp.get("group_name", "")
            for tr in grp.get("tr_list", []):
                code = tr.get("code", "").strip()
                if not code:
                    continue

                tr_name = tr.get("name", "")
                tr_class = classify_tr(code, tr.get("response_body", []), category, tr.get("example", {}).get("request", {}))
                market = CATEGORY_TO_MARKET.get(category, "etc")

                req_blocks = parse_blocks(tr.get("request_body", []), "InBlock", False)
                res_blocks = parse_blocks(tr.get("response_body", []), "OutBlock", True)

                continuation = detect_continuation(
                    code,
                    tr.get("request_body", []),
                    tr.get("response_body", []),
                    tr.get("example", {}).get("response", {}),
                )

                ex_req = tr.get("example", {}).get("request", {})
                ex_res = tr.get("example", {}).get("response", {})

                # 한 줄 TR dict 생성 (compact)
                lines.append(f'    "{code}": {{')
                lines.append(f'        "n": {json.dumps(tr_name, ensure_ascii=False)},')
                lines.append(f'        "c": {json.dumps(tr_class)},')
                lines.append(f'        "m": {json.dumps(market)},')
                lines.append(f'        "cat": {json.dumps(category, ensure_ascii=False)},')
                lines.append(f'        "grp": {json.dumps(group, ensure_ascii=False)},')

                # Request blocks
                lines.append(f'        "rb": [')
                for b in req_blocks:
                    lines.append(f'            {{"n": {json.dumps(b["name"])}, "f": [')
                    for f in b["fields"]:
                        lines.append(f'                {{"n": {json.dumps(f["n"])}, "k": {json.dumps(f["k"], ensure_ascii=False)}, "t": {json.dumps(f["t"])}, "l": {json.dumps(f["l"])}, "r": {fmt_bool(f["r"])}}},')
                    lines.append(f'            ], "r": {fmt_bool(b["is_repeating"])}}},')
                lines.append(f'        ],')

                # Response blocks
                lines.append(f'        "pb": [')
                for b in res_blocks:
                    lines.append(f'            {{"n": {json.dumps(b["name"])}, "f": [')
                    for f in b["fields"]:
                        lines.append(f'                {{"n": {json.dumps(f["n"])}, "k": {json.dumps(f["k"], ensure_ascii=False)}, "t": {json.dumps(f["t"])}, "l": {json.dumps(f["l"])}, "r": {fmt_bool(f["r"])}}},')
                    lines.append(f'            ], "r": {fmt_bool(b["is_repeating"])}}},')
                lines.append(f'        ],')

                # Continuation
                if continuation:
                    lines.append(f'        "cont": {{')
                    lines.append(f'            "db": {json.dumps(continuation["data_block"])},')
                    lines.append(f'            "cb": {json.dumps(continuation["continuation_block"])},')
                    lines.append(f'            "kf": {json.dumps(continuation["key_fields"])},')
                    lines.append(f'            "stop": {json.dumps(continuation["stop_condition"])},')
                    lines.append(f'        }},')

                # Examples
                if not ex_req:
                    lines.append(f'        "er": {{}},')
                else:
                    ex_req_str = json.dumps(ex_req, ensure_ascii=False, separators=(",", ":"))
                    lines.append(f'        "er": {ex_req_str.replace("null", "None")},')
                if not ex_res:
                    lines.append(f'        "ep": {{}},')
                else:
                    ex_res_str = json.dumps(ex_res, ensure_ascii=False, separators=(",", ":"))
                    lines.append(f'        "ep": {ex_res_str.replace("null", "None")},')

                lines.append(f'    }},')
                count += 1

    lines.append("}")
    lines.append("")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    file_size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"✅ 완료: {count}개 TR → {OUTPUT_PATH} ({file_size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
