.PHONY: deps

deps:
	@if xcode-select -p >/dev/null 2>&1; then \
		echo "✅ Xcode Command Line Tools already installed"; \
	else \
		echo "Installing Xcode Command Line Tools..."; \
		xcode-select --install; \
	fi
	swift package resolve
