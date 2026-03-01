.PHONY: deps test lint apple-check

deps:
	@command -v uv >/dev/null 2>&1 || { echo "Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }
	uv sync
ifeq ($(shell uname),Darwin)
	@xcode-select -p >/dev/null 2>&1 || { echo "Error: macOS Command Line Tools are not installed.\nInstall them by running:\n\n  xcode-select --install\n"; exit 1; }
endif

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/

apple-check:
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "Building Apple check binary..."; \
		cd checks/apple && swift build -c release; \
	else \
		echo "Apple check requires macOS"; \
		exit 1; \
	fi
