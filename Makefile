PYTHON ?= python3
VENV_PYTHON := .venv/bin/python
FRONTEND_URL ?=
API_BASE_URL ?=
SLOW_MO_MS ?=
HOLD_OPEN_SECONDS ?=
ARTIFACTS_DIR ?=
DATA_BUCKET ?=
KNOWLEDGE_BASE_ID ?=
DATA_SOURCE_ID ?=
AWS_REGION ?= us-east-2
QA_ARGS :=

ifneq ($(strip $(FRONTEND_URL)),)
QA_ARGS += --frontend-url "$(FRONTEND_URL)"
endif

ifneq ($(strip $(API_BASE_URL)),)
QA_ARGS += --api-base-url "$(API_BASE_URL)"
endif

ifneq ($(strip $(SLOW_MO_MS)),)
QA_ARGS += --slow-mo-ms $(SLOW_MO_MS)
endif

ifneq ($(strip $(HOLD_OPEN_SECONDS)),)
QA_ARGS += --hold-open-seconds $(HOLD_OPEN_SECONDS)
endif

ifneq ($(strip $(ARTIFACTS_DIR)),)
QA_ARGS += --artifacts-dir "$(ARTIFACTS_DIR)"
endif

.PHONY: setup-local-browser-tests qa-local-frontend qa-local-frontend-reuse qa-local-frontend-headed build-kb-index sync-kb-index eval-rag

# Local lexical recall + citation attribution against data/kb/golden_queries.json
eval-rag:
	$(PYTHON) -m unittest tests.test_rag_eval -v

build-kb-index:
	$(PYTHON) tools/build_kb_index.py \
		--input data/recipes_json/recipes.json \
		--output-dir data/kb

# Requires: DATA_BUCKET, and for ingestion KNOWLEDGE_BASE_ID + DATA_SOURCE_ID (stack outputs).
sync-kb-index: build-kb-index
	@test -n "$(DATA_BUCKET)" || (echo "Set DATA_BUCKET=<DataBucketName stack output>" >&2; exit 1)
	$(PYTHON) tools/sync_kb_index.py \
		--local-dir data/kb \
		--bucket "$(DATA_BUCKET)" \
		--region "$(AWS_REGION)" \
		$(if $(KNOWLEDGE_BASE_ID),--knowledge-base-id "$(KNOWLEDGE_BASE_ID)",) \
		$(if $(DATA_SOURCE_ID),--data-source-id "$(DATA_SOURCE_ID)",)

setup-local-browser-tests:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements-dev.txt

qa-local-frontend:
	$(VENV_PYTHON) tools/run_local_frontend_e2e.py $(QA_ARGS)

qa-local-frontend-reuse:
	$(VENV_PYTHON) tools/run_local_frontend_e2e.py --reuse-existing-only $(QA_ARGS)

qa-local-frontend-headed:
	$(VENV_PYTHON) tools/run_local_frontend_e2e.py --headed $(QA_ARGS)
