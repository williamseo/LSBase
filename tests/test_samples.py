"""모든 샘플 파일 문법 검증 (네트워크 호출 없음)"""
import sys
sys.path.insert(0, '.')

import ast
import os
import pytest

SAMPLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = [
    f for f in os.listdir(SAMPLE_DIR)
    if f.endswith('.py') and (f.startswith('sample_') or f.startswith('full_'))
]
SAMPLES += ['searchtr.py']


@pytest.mark.parametrize('filename', SAMPLES)
def test_sample_syntax(filename):
    path = os.path.join(SAMPLE_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(f'{filename} not found')
    with open(path) as f:
        ast.parse(f.read())
