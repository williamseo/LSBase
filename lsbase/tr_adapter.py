import json
import re
import warnings
from typing import Dict, Any, List, Optional

# --- Helper Functions ---

def _sanitize_name(name: str) -> str:
    """
    JSON의 이름을 파이썬 속성명으로 사용 가능하게 정제합니다.
    괄호나 대괄호 안의 내용을 보존하여 이름 충돌을 최소화합니다.
    예: "업종차트(틱/n틱)" -> "업종차트_틱_n틱"
    """
    if not isinstance(name, str):
        return ''
        
    # 괄호와 대괄호를 언더스코어(_)로 치환
    name = name.replace('(', '_').replace(')', '')
    name = name.replace('[', '_').replace(']', '')
    
    # 파이썬 변수명으로 사용할 수 없는 문자들을 언더스코어(_)로 변경
    name = re.sub(r'[^a-zA-Z0-9가-힣_]', '_', name).strip()
    
    # 연속된 언더스코어를 하나로 축약
    name = re.sub(r'_+', '_', name)
    
    # 시작과 끝의 언더스코어 제거
    name = name.strip('_')
    
    # 이름이 비어있거나 숫자로 시작하는 경우를 방지
    if not name or name[0].isdigit():
        name = 'TR_' + name # 접두사 추가
        
    return name

def _clean_field_name(name: str) -> str:
    """API 명세의 필드 이름에서 불필요한 HTML 엔티티와 공백 등을 제거합니다."""
    if not isinstance(name, str):
        return ''
    return name.replace('&nbsp;', '').strip().lstrip('-').strip()


# --- Core Classes ---

class TrSpec:
    """
    하나의 TR에 대한 모든 상세 명세를 캡슐화하는 클래스입니다.
    이 객체는 TR 코드, 이름, 요청/응답 구조, 예제 데이터 등을 속성으로 가집니다.
    """
    def __init__(self, spec_data: Dict[str, Any]):
        self.name: Optional[str] = spec_data.get('name')
        self.code: str = spec_data.get('code', '').strip()
        self.tps: Optional[str] = spec_data.get('transaction_per_sec')
        
        structure: Dict[str, List[Dict[str, Any]]] = spec_data.get('structure', {})
        self.request_header: List[Dict[str, Any]] = structure.get('request_header', [])
        self.request_body: List[Dict[str, Any]] = structure.get('request_body', [])
        self.response_header: List[Dict[str, Any]] = structure.get('response_header', [])
        self.response_body: List[Dict[str, Any]] = structure.get('response_body', [])

        example: Dict[str, str] = spec_data.get('example', {})
        try:
            self.example_request: Dict[str, Any] = json.loads(example.get('request', '{}'))
        except (json.JSONDecodeError, TypeError):
            self.example_request = {}
        try:
            self.example_response: Dict[str, Any] = json.loads(example.get('response', '{}'))
        except (json.JSONDecodeError, TypeError):
            self.example_response = {}

    def get_request_template(self) -> Dict[str, Dict[str, str]]:
        """
        API 요청 본문의 InBlock 템플릿을 생성하여 반환합니다.
        필수 필드와 그 설명을 포함하여 개발자가 어떤 값을 넣어야 할지 쉽게 알 수 있도록 돕습니다.
        """
        template: Dict[str, Dict[str, str]] = {}
        current_block: Optional[str] = None
        
        for field in self.request_body:
            field_name: str = _clean_field_name(field.get('name', ''))
            
            # InBlock 시작을 감지 (e.g., "CSPAT00601InBlock")
            if 'InBlock' in field_name:
                current_block = field_name
                template[current_block] = {}
                continue
            
            if current_block:
                # 필드 정보를 템플릿에 추가
                is_required: bool = field.get('required', 'N').upper() == 'Y'
                description: str = field.get('description') or "설명 없음" # None일 경우 대비
                
                # 플레이스홀더 텍스트 생성
                req_text = "필수" if is_required else "선택"
                placeholder = f"{req_text}: {field.get('korean_name', '')} ({description})"
                
                template[current_block][field_name] = placeholder

        return template

    def __repr__(self) -> str:
        return f"<TrSpec: {self.code} ({self.name})>"

class ApiNode:
    """API의 중간 계층(카테고리, 그룹)을 나타내는 노드 클래스"""
    def __init__(self, name: str):
        self._name = name

    def __repr__(self) -> str:
        children: List[str] = [k for k in self.__dict__.keys() if not k.startswith('_')]
        return f"<ApiNode '{self._name}' with children: {children}>"

class TrCodeAdapter:
    """
    단일 통합 API 명세 JSON 파일을 읽어 API 전체를 표현하는 어댑터 클래스입니다.
    """
    def __init__(self, specs_filepath: str):
        """
        어댑터를 초기화하고 통합 명세 파일을 로드하여 API 트리 구조를 빌드합니다.
        
        :param specs_filepath: 모든 TR의 구조와 명세가 담긴 통합 JSON 파일 경로.
        """
        try:
            with open(specs_filepath, 'r', encoding='utf-8') as f:
                self._specs_data: List[Dict[str, Any]] = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"통합 명세 파일 없음: {specs_filepath}")
        except json.JSONDecodeError:
            raise ValueError(f"통합 명세 파일 JSON 형식 오류: {specs_filepath}")
        
        self._tr_code_map: Dict[str, Dict] = {} # 역방향 조회를 위한 맵
        self._build_api_tree()

    def _build_api_tree(self) -> None:
        """통합 명세 데이터를 직접 순회하며 API 트리를 빌드합니다."""
        for category_data in self._specs_data:
            cat_name = _sanitize_name(category_data.get('category', ''))
            if not cat_name: continue

            if not hasattr(self, cat_name):
                setattr(self, cat_name, ApiNode(cat_name))
            category_node = getattr(self, cat_name)

            for group_data in category_data.get('api_groups', []):
                group_name = _sanitize_name(group_data.get('group_name', ''))
                if not group_name: continue

                if not hasattr(category_node, group_name):
                    setattr(category_node, group_name, ApiNode(f"{cat_name}.{group_name}"))
                api_group_node = getattr(category_node, group_name)
                
                for tr_spec_data in group_data.get('tr_list', []):
                    tr_name = _sanitize_name(tr_spec_data.get('name', ''))
                    tr_code = tr_spec_data.get('code', '').strip()
                    if not tr_name or not tr_code: continue
                    
                    # TrSpec 객체 생성
                    tr_spec_object = TrSpec(tr_spec_data)
                    
                    # 역방향 조회를 위해 TR 코드 맵에 데이터 추가
                    self._tr_code_map[tr_code] = tr_spec_data
                    
                    if hasattr(api_group_node, tr_name):
                        old_spec = getattr(api_group_node, tr_name)
                        warnings.warn(
                            f"속성명 충돌: '{cat_name}.{group_name}.{tr_name}'이 중복됩니다. "
                            f"기존 TR '{old_spec.code}'을(를) 새 TR '{tr_spec_object.code}'(으)로 덮어씁니다."
                        )

                    setattr(api_group_node, tr_name, tr_spec_object)

    def find_by_code(self, code: str) -> Optional[TrSpec]:
        """
        TR 코드로 해당하는 TrSpec 객체를 찾아서 반환합니다.
        
        :param code: 검색할 TR 코드 (e.g., "t1102")
        :return: 찾은 TrSpec 객체 또는 None
        """
        target_code = code.strip()
        spec_data = self._tr_code_map.get(target_code)
        return TrSpec(spec_data) if spec_data else None

    def __repr__(self) -> str:
        categories = [k for k, v in self.__dict__.items() if isinstance(v, ApiNode)]
        return f"<TrCodeAdapter with categories: {categories}>"
