# tools/generate_code.py (v9.2 - 최종)
import json
import os
import re
from jinja2 import Environment, FileSystemLoader

# --- 상수 정의 ---
OUTPUT_FILENAME = "../generated_models.py"
SPECS_FILENAME = "ls_openapi_specs.json"
TEMPLATE_NAME = "api_client_template.py.jinja2"

# --- 헬퍼 함수 ---
def to_pascal_case(name: str) -> str:
    if not isinstance(name, str) or not name: return "UnnamedBlock"
    name = re.sub(r'[^a-zA-Z0-9]', '', name)
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return ''.join(word.capitalize() for word in s2.split('_'))

def map_type_to_python(api_type_code: str, length: str) -> str:
    if isinstance(length, str) and '.' in length: return "float"
    type_map = {"A0003": "int", "A0004": "int", "A0006": "float"}
    return type_map.get(api_type_code, "str")

def get_field_specs_dict(spec_list: list) -> dict:
    defs = {}
    if not spec_list: return defs
    for p in spec_list:
        p_name = p.get("name", "").strip()
        if p_name and 'InBlock' not in p_name and 'OutBlock' not in p_name:
            defs[p_name] = {
                "korean_name": p.get("korean_name", "N/A"),
                "type": map_type_to_python(p.get("type"), p.get("length")),
                "length": p.get("length", "N/A"),
            }
    return defs

# ★★★★★ 여기가 핵심 수정 부분입니다 ★★★★★
def infer_type_from_value(value: any, spec_type: str) -> str:
    """명세 타입과 샘플 값 타입을 종합하여 가장 정확한 타입을 추론합니다."""
    # 1. 샘플 값이 순수 int/float이면 가장 신뢰
    if isinstance(value, int): return "int"
    if isinstance(value, float): return "float"

    # 2. 명세가 str이면, 샘플 값이 숫자처럼 생겨도 str 유지 (가장 중요!)
    if spec_type == "str":
        return "str"

    # 3. 명세가 숫자 타입인데, 샘플이 문자열 형태의 숫자인 경우 변환
    if isinstance(value, str):
        if spec_type == "float" and value.replace('.', '', 1).replace('-', '', 1).isdigit():
            return "float"
        if spec_type == "int" and value.replace('-', '', 1).isdigit():
            return "int"
    
    # 4. 모든 규칙에 해당 없으면 명세 타입을 따름
    return spec_type
# ★★★★★ 수정 끝 ★★★★★

def get_fields_as_string(fields_data: list, is_realtime: bool = False) -> str:
    if not fields_data: return "    pass"
    field_strings = []
    for field in fields_data:
        escaped_desc = field['description'].replace('"', '\\"').replace('\n', ' ').replace('\r', '')
        if is_realtime:
            line = f"    {field['name']}: Optional[{field['type']}] = Field(default=None, description=\"{escaped_desc}\")"
        else:
            line = f"    {field['name']}: {field['type']} = Field(..., description=\"{escaped_desc}\")"
        field_strings.append(line)
    return "\n".join(field_strings)

def analyze_json_structure(sample_data: dict, block_name: str, field_specs: dict) -> list:
    # (이하 main 함수까지 수정 없음)
    models = []
    if not isinstance(sample_data, dict): return []
    main_model_fields = []
    for key, value in sample_data.items():
        class_name = to_pascal_case(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            item_class_name = f"{class_name}Item"
            item_fields_data = []
            for field_name, field_value in value[0].items():
                spec = field_specs.get(field_name, {})
                base_type = spec.get("type", "str")
                final_type = infer_type_from_value(field_value, base_type)
                final_desc = f"{spec.get('korean_name', '설명 없음')} (길이: {spec.get('length', 'N/A')})"
                item_fields_data.append({"name": field_name, "type": final_type, "description": final_desc})
            models.append({"class_name": item_class_name, "fields_str": get_fields_as_string(item_fields_data)})
            main_model_fields.append({"name": key, "type": f"List[{item_class_name}]", "description": f"{key} 블록"})
        elif isinstance(value, dict):
            sub_model_fields_data = []
            for field_name, field_value in value.items():
                spec = field_specs.get(field_name, {})
                base_type = spec.get("type", "str")
                final_type = infer_type_from_value(field_value, base_type)
                final_desc = f"{spec.get('korean_name', '설명 없음')} (길이: {spec.get('length', 'N/A')})"
                sub_model_fields_data.append({"name": field_name, "type": final_type, "description": final_desc})
            models.append({"class_name": class_name, "fields_str": get_fields_as_string(sub_model_fields_data)})
            main_model_fields.append({"name": key, "type": class_name, "description": f"{key} 블록"})
        else:
            spec = field_specs.get(key, {})
            base_type = spec.get("type", "str")
            final_type = infer_type_from_value(value, base_type)
            main_model_fields.append({"name": key, "type": final_type, "description": f"{spec.get('korean_name', key)}"})
    main_class_name = to_pascal_case(block_name)
    models.append({"class_name": main_class_name, "fields_str": get_fields_as_string(main_model_fields)})
    return models

def main():
    print("Pydantic 모델 코드 생성을 시작합니다 (v9.2 최종)...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    specs_path = os.path.join(script_dir, SPECS_FILENAME)
    output_path = os.path.join(script_dir, OUTPUT_FILENAME)
    if not os.path.exists(specs_path):
        print(f"❌ 오류: '{specs_path}' 파일을 찾지 못했습니다.")
        return

    env = Environment(loader=FileSystemLoader(script_dir))
    template = env.get_template(TEMPLATE_NAME)
    with open(specs_path, 'r', encoding='utf-8') as f:
        specs_data = json.load(f)

    all_tr_specs = []
    for category in specs_data:
        for group in category.get('api_groups', []):
            for tr in group.get('tr_list', []):
                tr_code = tr.get('code', '').strip()
                if not tr_code: continue
                req_example = tr['example'].get('request', {})
                if not isinstance(req_example, dict): req_example = {}
                req_field_specs = get_field_specs_dict(tr.get('request_body', []))
                req_models = analyze_json_structure(req_example, f"{tr_code}Request", req_field_specs)
                res_models = []
                is_realtime_tr = not tr_code.startswith('t') and not tr_code.startswith('C')
                if is_realtime_tr:
                    print(f"   - 정보: 실시간 TR '{tr_code}'의 모델을 명세 기반으로 생성합니다.")
                    res_field_specs = get_field_specs_dict(tr.get('response_body', []))
                    realtime_fields = []
                    for field_name, spec in res_field_specs.items():
                        field_type = spec.get("type", "str")
                        field_desc = f"{spec.get('korean_name', '설명 없음')} (길이: {spec.get('length', 'N/A')})"
                        realtime_fields.append({"name": field_name, "type": field_type, "description": field_desc})
                    class_name = f"{to_pascal_case(tr_code)}Response"
                    fields_str = get_fields_as_string(realtime_fields, is_realtime=True)
                    res_models = [{"class_name": class_name, "fields_str": fields_str}]
                else:
                    res_example = tr['example'].get('response', {})
                    if not isinstance(res_example, dict): res_example = {}
                    res_field_specs = get_field_specs_dict(tr.get('response_body', []))
                    res_models = analyze_json_structure(res_example, f"{tr_code}Response", res_field_specs)
                all_tr_specs.append({
                    "code": tr_code, "name": tr.get('name'),
                    "request_models": req_models,
                    "response_models": res_models,
                })
    
    rendered_code = template.render(tr_specs=all_tr_specs)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rendered_code)
    print(f"✅ 성공! '{os.path.abspath(output_path)}' 파일이 생성되었습니다.")

if __name__ == "__main__":
    main()
