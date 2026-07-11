.PHONY: install install-py install-ui dev dev-api dev-processor dev-ui build lint help

# ── Configuration ────────────────────────────────────────────────────────────
CORE_PORT    := 8000
PROCESSOR_PORT := 8010
UI_PORT      := 5173

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "memward — available targets"
	@echo ""
	@echo "  make install        Install all Python and UI dependencies"
	@echo "  make install-py     Install Python dependencies only (uv sync)"
	@echo "  make install-ui     Install UI dependencies only (npm install)"
	@echo ""
	@echo "  make dev            Print instructions to run all 3 dev servers"
	@echo "  make dev-api        Run core API on port $(CORE_PORT)"
	@echo "  make dev-processor  Run processor on port $(PROCESSOR_PORT)"
	@echo "  make dev-ui         Run curation UI on port $(UI_PORT)"
	@echo ""
	@echo "  make build          Build the curation UI for production"
	@echo "  make lint           Run Python type check + UI linter"
	@echo ""

# ── Install ───────────────────────────────────────────────────────────────────
install: install-py install-ui
	@echo ""
	@echo "✓ All dependencies installed."
	@echo "  Next: copy .env.example to .env and fill in your credentials."
	@echo ""

install-py:
	uv sync

install-ui:
	cd ui && npm install

# ── Dev servers ───────────────────────────────────────────────────────────────
dev:
	@echo ""
	@echo "Run each of the following in a separate terminal:"
	@echo ""
	@echo "  Terminal 1 — Core API:"
	@echo "    make dev-api"
	@echo ""
	@echo "  Terminal 2 — Processor:"
	@echo "    make dev-processor"
	@echo ""
	@echo "  Terminal 3 — Curation UI:"
	@echo "    make dev-ui"
	@echo ""
	@echo "  Then open http://localhost:$(UI_PORT)"
	@echo ""

dev-api:
	uv run uvicorn core.main:app --app-dir src --host 127.0.0.1 --port $(CORE_PORT) --reload

dev-processor:
	uv run uvicorn processor.main:app --app-dir src --host 127.0.0.1 --port $(PROCESSOR_PORT) --reload

dev-ui:
	cd ui && npm run dev

# ── Build ─────────────────────────────────────────────────────────────────────
build:
	cd ui && npm run build
	@echo ""
	@echo "✓ UI built to src/ui/dist/"
	@echo "  The core API will serve it at http://127.0.0.1:$(CORE_PORT)/ui"
	@echo ""

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	cd ui && npm run lint
