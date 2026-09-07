.PHONY: deps test lint apple-check

deps:
	bin/setup

test:
	bin/test

lint:
	bin/lint

apple-check:
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "Building Apple check binary..."; \
		cd checks/apple && swift build -c release; \
	else \
		echo "Apple check requires macOS"; \
		exit 1; \
	fi
