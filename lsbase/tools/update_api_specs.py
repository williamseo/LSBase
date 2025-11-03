# lsbase/tools/update_api_specs.py

import requests
import json
from bs4 import BeautifulSoup
import time
import argparse
import sys
import os
from tqdm import tqdm
from typing import List, Dict, Any, Optional

BASE_URL = "https://openapi.ls-sec.co.kr"
OVERVIEW_FILENAME = "ls_tr_overview.json"
FULL_SPECS_FILENAME = "ls_openapi_specs.json"

def get_property_type_mapping() -> Dict[str, str]:
    """프로퍼티 타입 코드를 실제 타입 이름으로 변환하기 위한 매핑 정보를 가져옵니다."""
    url = f"{BASE_URL}/api/codes/public/system-codes?groupCode=property_type"
    mapping = {}
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'list' in data:
            mapping = {c['code']: c['name'] for c in data['list']}
        else: # Fallback for unexpected structure
             mapping = {c['code']: c['name'] for c in data}
    except requests.exceptions.RequestException as e:
        print(f"   - 경고: 프로퍼티 타입 매핑 정보를 가져오지 못했습니다: {e}")
        print("   - 기본 타입(string, long 등)으로 대치합니다.")
    return mapping

def get_menu_structure() -> List[Dict[str, Any]]:
    """웹페이지의 메뉴 구조를 파싱하여 카테고리, API 그룹, ID 목록을 가져옵니다."""
    url = f"{BASE_URL}/apiservice"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    menu_structure = []

    lnb = soup.find('nav', id='lnb')
    category_items = lnb.find_all('li', id=True)

    for item in category_items:
        category_name_tag = item.select_one('ul.second-depth > li > a')
        if not category_name_tag:
            continue

        category_name = category_name_tag.text.strip()
        if ']' in category_name:
            category_name = category_name.split(']')[0].replace('[', '')

        category_data = {
            "category_name": category_name,
            "api_groups": []
        }

        for sub_item in item.select('ul.third-depth > li[id]'):
            category_data["api_groups"].append({
                "api_name": sub_item.find('a').text.strip(),
                "api_id": sub_item['id']
            })

        if category_data["api_groups"]:
            menu_structure.append(category_data)

    return menu_structure

def get_tr_list_from_api_id(api_id: str) -> Optional[List[Dict[str, Any]]]:
    """api_id를 기반으로 해당 API의 TR 목록 정보를 가져옵니다."""
    url = f"{BASE_URL}/api/apis/guide/tr/{api_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

def get_tr_properties(tr_id: str) -> Optional[List[Dict[str, Any]]]:
    """tr_id를 기반으로 해당 TR의 상세 속성(요청/응답) 정보를 가져옵니다."""
    url = f"{BASE_URL}/api/apis/guide/tr/property/{tr_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

# --- 모드별 실행 함수 ---

def run_overview_mode(menu: List[Dict[str, Any]]):
    """[빠른 모드] TR 목록만 포함된 `ls_tr_overview.json` 파일을 생성합니다."""
    print(f"\n🚀 빠른 'overview' 모드를 실행합니다... ({OVERVIEW_FILENAME} 생성)")
    overview_data = []

    for category in tqdm(menu, desc="카테고리 처리 중"):
        category_overview = { "category": category['category_name'], "api_groups": [] }
        for api_group in category['api_groups']:
            tr_list = get_tr_list_from_api_id(api_group['api_id'])
            time.sleep(0.05)
            if not tr_list: continue
            
            api_group_overview = {
                "group_name": api_group['api_name'],
                "tr_list": [{"name": tr.get('trName'), "code": tr.get('trCode')} for tr in tr_list]
            }
            category_overview['api_groups'].append(api_group_overview)
        overview_data.append(category_overview)

    with open(OVERVIEW_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(overview_data, f, ensure_ascii=False, indent=4)
    print(f"\n✅ '{OVERVIEW_FILENAME}' 파일이 성공적으로 생성되었습니다.")


def run_full_mode(menu: List[Dict[str, Any]], prop_type_map: Dict[str, str]):
    """[전체 모드] 모든 TR의 상세 명세를 포함한 `ls_openapi_specs.json` 파일을 생성합니다."""
    print(f"\n🐢 전체 'full' 모드를 실행합니다... (시간이 다소 걸릴 수 있습니다. {FULL_SPECS_FILENAME} 생성)")
    
    data = []
    
    for cat in tqdm(menu, desc="카테고리 상세 처리 중"):
        c = {"category": cat["category_name"], "api_groups": []}
        
        for grp in tqdm(cat["api_groups"], desc=f"  {cat['category_name']} 그룹 처리 중", leave=False):
            trs = get_tr_list_from_api_id(grp["api_id"])
            if not trs: continue
            
            g = {"group_name": grp["api_name"], "tr_list": []}
            
            for tr in trs:
                time.sleep(0.05)
                props = get_tr_properties(tr["id"])
                if not props: continue

                # simplify 함수를 수정하여 'description' 키가 없는 경우에도 안전하게 처리
                def simplify(block):
                    return [{
                        "name": p.get("propertyCd", "").replace("&nbsp;", "").replace("-", "").strip(),
                        "korean_name": p.get("propertyNm"),
                        "type": prop_type_map.get(p.get("propertyType"), p.get("propertyType")),
                        "length": p.get("propertyLength"),
                        "required": p.get("requireYn", "N"),
                        "description": p.get("description", "")  # .get()을 사용하여 키가 없으면 빈 문자열 반환
                    } for p in props if p.get("bodyType") == block]
                
                req_body_spec = simplify("req_b")
                res_body_spec = simplify("res_b")
                
                req_example = tr.get("reqExample")
                res_example = tr.get("resExample")
                try:
                    req_example_json = json.loads(req_example) if isinstance(req_example, str) else req_example
                except (json.JSONDecodeError, TypeError):
                    req_example_json = {}
                try:
                    res_example_json = json.loads(res_example) if isinstance(res_example, str) else res_example
                except (json.JSONDecodeError, TypeError):
                    res_example_json = {}

                g["tr_list"].append({
                    "name": tr.get("trName"),
                    "code": tr.get("trCode"),
                    "description": tr.get("description", ""), # .get() 사용
                    "request_header": simplify("req_h"),
                    "request_body": req_body_spec,
                    "response_header": simplify("res_h"),
                    "response_body": res_body_spec,
                    "example": {
                        "request": req_example_json,
                        "response": res_example_json
                    }
                })
            
            if g["tr_list"]:
                c["api_groups"].append(g)
        
        if c["api_groups"]:
            data.append(c)

    with open(FULL_SPECS_FILENAME, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ '{FULL_SPECS_FILENAME}' 파일이 성공적으로 생성되었습니다.")

def main():
    """스크립트의 메인 진입점. 커맨드 라인 인자를 파싱하여 적절한 모드를 실행합니다."""
    parser = argparse.ArgumentParser(
        description="LS증권 API 명세 스크레이퍼. 인자 없이 실행 시 필요한 파일이 없으면 전체 자동 생성합니다.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "mode",
        choices=['overview', 'full'],
        nargs='?',
        default=None,
        help=(
            "스크레이퍼 실행 모드를 선택합니다.\n"
            "'overview': 빠르지만 TR 목록만 생성\n"
            "'full'    : 느리지만 전체 상세 명세 생성\n"
            "(생략)    : 두 JSON 파일이 모두 없으면 'overview'와 'full'을 순차적으로 실행"
        )
    )
    args = parser.parse_args()

    try:
        print("스크레이핑을 시작합니다...")
        
        if args.mode:
            menu = get_menu_structure()
            if args.mode == 'overview':
                run_overview_mode(menu)
            elif args.mode == 'full':
                prop_type_map = get_property_type_mapping()
                run_full_mode(menu, prop_type_map)
        else:
            overview_exists = os.path.exists(OVERVIEW_FILENAME)
            full_specs_exists = os.path.exists(FULL_SPECS_FILENAME)

            if not overview_exists or not full_specs_exists:
                print("\n필요한 JSON 파일이 없어 전체 자동 생성을 시작합니다.")
                menu = get_menu_structure()
                prop_type_map = get_property_type_mapping()
                
                if not overview_exists:
                    run_overview_mode(menu)
                
                if not full_specs_exists:
                    run_full_mode(menu, prop_type_map)
            else:
                print(f"\n✅ 모든 API 명세 파일 ('{OVERVIEW_FILENAME}', '{FULL_SPECS_FILENAME}')이 이미 존재합니다.")
                print("다시 생성하려면 원하는 모드를 직접 지정하여 실행하세요.")
                print(f"  - 예시: python {sys.argv[0]} full")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ 치명적인 오류 발생: LS증권 서버에 접속할 수 없습니다. ({e})")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 알 수 없는 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
