"""모든 샘플 파일 문법 검증 (네트워크 호출 없음)"""
import sys
sys.path.insert(0, '.')

import ast
import os
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DIR = os.path.join(BASE_DIR, 'samples')
SAMPLES = [
    os.path.join(SAMPLE_DIR, f)
    for f in os.listdir(SAMPLE_DIR)
    if f.endswith('.py') and (f.startswith('sample_') or f.startswith('full_'))
]
SAMPLES += [os.path.join(BASE_DIR, 'tools', 'searchtr.py')]


@pytest.mark.parametrize('filepath', SAMPLES)
def test_sample_syntax(filepath):
    if not os.path.exists(filepath):
        pytest.skip(f'{filepath} not found')
    with open(filepath) as f:
        ast.parse(f.read())
