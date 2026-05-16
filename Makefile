.PHONY: install test specs search validate clean help samples

PYTHON := python3

help: ## 이 도움말 출력
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## pip 의존성 설치
	$(PYTHON) -m pip install -r requirements.txt

test: ## pytest 실행
	$(PYTHON) -m pytest tests/ -v $(ARGS)

specs: ## TR 명세 생성 (최초 1회)
	PYTHONPATH=. $(PYTHON) lsbase/tools/generate_specs.py

search: ## TR 검색: make search ARGS="t1102"  또는  make search ARGS="--search 현재가"
	PYTHONPATH=. $(PYTHON) tools/searchtr.py $(ARGS)

validate: ## 실제 API 응답 vs TR 명세 검증: make validate ARGS="t1102"
	PYTHONPATH=. $(PYTHON) tools/validate_spec.py $(ARGS)

samples: ## 샘플 목록 출력
	@echo "=== 샘플 파일 목록 (samples/) ==="
	@ls -1 samples/sample_*.py samples/full_order_cycle.py samples/news.py 2>/dev/null | \
		while read f; do \
			name=$$(basename $$f .py); \
			desc=$$(grep -m1 '"""' $$f 2>/dev/null | sed 's/"""//g' || echo "---"); \
			printf "  \033[36m%-35s\033[0m %s\n" "$$name" "$$desc"; \
		done
	@echo ""
	@echo "실행: PYTHONPATH=. $(PYTHON) samples/<파일명>.py"

clean: ## __pycache__ / .pytest_cache / .venv 등 임시 파일 정리
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.mypy_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv/ 2>/dev/null || true
	@echo "✅ 캐시 정리 완료"
