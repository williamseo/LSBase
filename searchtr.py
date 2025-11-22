# searchtr.py (여러 TR 코드 검색 및 토큰 값 제거 기능 추가)
import json
import argparse
import sys
from typing import Any

# 상위 디렉토리에서 실행될 것을 가정하고 파일 경로를 설정합니다.
SPECS_FILE_PATH = 'lsbase/tools/ls_openapi_specs.json'

def find_tr_spec(all_specs: list, tr_code_to_find: str):
    """
    미리 로드된 전체 명세 데이터에서 지정된 TR 코드를 찾아 반환합니다.

    :param all_specs: ls_openapi_specs.json 파일의 전체 내용 (리스트)
    :param tr_code_to_find: 찾고자 하는 TR 코드 (예: "t1102")
    :return: 찾은 TR 명세 딕셔너리 또는 None
    """
    for category in all_specs:
        for group in category.get('api_groups', []):
            for tr_spec in group.get('tr_list', []):
                if tr_spec.get('code', '').strip() == tr_code_to_find:
                    return tr_spec
    
    return None

# ★★★★★ 여기가 추가된 부분입니다 ★★★★★
def sanitize_spec_data(data: Any):
    """
    명세 데이터(딕셔너리 또는 리스트)를 재귀적으로 순회하며
    'token' 키의 값을 짧은 문자열로 대체합니다.

    :param data: 수정할 데이터 (딕셔너리 또는 리스트)
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "token" and isinstance(value, str):
                data[key] = "<ACCESS_TOKEN_REMOVED>"
            else:
                sanitize_spec_data(value) # 재귀 호출
    elif isinstance(data, list):
        for item in data:
            sanitize_spec_data(item) # 재귀 호출
# ★★★★★ 추가 끝 ★★★★★

def main():
    """
    스크립트의 메인 실행 함수입니다.
    """
    parser = argparse.ArgumentParser(
        description="LS증권 API 명세 파일에서 특정 TR 코드의 상세 내용을 검색합니다.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "tr_codes",
        nargs='+',
        type=str,
        help="검색할 TR 코드를 하나 이상 입력하세요 (공백으로 구분).\n예시: python searchtr.py t1102 CSPAT00601"
    )
    args = parser.parse_args()

    try:
        with open(SPECS_FILE_PATH, 'r', encoding='utf-8') as f:
            all_specs_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 오류: 명세 파일을 찾을 수 없습니다. '{SPECS_FILE_PATH}'")
        print("스크립트를 프로젝트 최상위 디렉토리에서 실행했는지 확인하세요.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ 오류: JSON 파일 형식이 올바르지 않습니다. '{SPECS_FILE_PATH}'")
        sys.exit(1)

    found_count = 0
    total_count = len(args.tr_codes)

    for i, tr_code in enumerate(args.tr_codes):
        if i > 0:
            print("\n" + "="*60 + "\n")

        target_tr_code = tr_code.strip()
        print(f"🔍 [{i+1}/{total_count}] '{target_tr_code}' TR 코드를 검색합니다...")

        found_spec = find_tr_spec(all_specs_data, target_tr_code)

        if found_spec:
            found_count += 1
            
            # ★★★★★ 여기가 수정된 부분입니다 ★★★★★
            # 출력하기 전에 찾은 명세 데이터에서 토큰 값을 정리합니다.
            sanitize_spec_data(found_spec)
            # ★★★★★ 수정 끝 ★★★★★

            print(f"✅ TR 코드를 찾았습니다: [ {found_spec.get('name', '이름 없음')} ({target_tr_code}) ]")
            print("-" * 50)
            
            pretty_json = json.dumps(
                found_spec, 
                indent=2, 
                ensure_ascii=False
            )
            print(pretty_json)
            print("-" * 50)
        else:
            print(f"😭 TR 코드 '{target_tr_code}'을(를) 찾을 수 없습니다.")

    #print("\n" + "="*60)
    #print(f"✨ 검색 완료. 총 {total_count}개 중 {found_count}개의 TR을 찾았습니다.")

if __name__ == "__main__":
    main()
