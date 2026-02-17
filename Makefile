.PHONY: deps test lint apple-check

deps:
	python3 -m venv .venv
	.venv/bin/python3 -m pip install -e ".[dev]"

test:
	.venv/bin/python3 -m pytest tests/ -v

lint:
	.venv/bin/ruff check src/ tests/

apple-check:
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "Building Apple check binary..."; \
		cd checks/apple && swift build -c release; \
	else \
		echo "Apple check requires macOS"; \
		exit 1; \
	fi
