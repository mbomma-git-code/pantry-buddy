PYTHON ?= python3
VENV_PYTHON := .venv/bin/python
FRONTEND_URL ?=
API_BASE_URL ?=
SLOW_MO_MS ?=
HOLD_OPEN_SECONDS ?=
ARTIFACTS_DIR ?=
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

.PHONY: setup-local-browser-tests qa-local-frontend qa-local-frontend-reuse qa-local-frontend-headed

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
