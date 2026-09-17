# mortgage-risk-platform
# Run `make check` before every commit. PROJECT.md section 10.
#
# On a host where security policy blocks execution of the local virtualenv,
# use the `docker-` targets instead. See docs/decisions/ADR-003-dev-environment.md.

.DEFAULT_GOAL := help
UV := uv
# Full bookworm, not slim: git is required by the hygiene tests and by
# detect-secrets, both of which enumerate tracked files.
DEV_IMAGE := mortgage-risk-dev:local
# MSYS_NO_PATHCONV stops Git Bash rewriting the container-side /w path into
# a Windows drive letter. It is inert on Linux and macOS.
export MSYS_NO_PATHCONV := 1
DOCKER_RUN := docker run --rm -v "$(CURDIR):/w" -w /w -e UV_PROJECT_ENVIRONMENT=/opt/venv -v mrp-dev-venv:/opt/venv -v mrp-ivy:/root/.ivy2.5.2 $(DEV_IMAGE)

.PHONY: help install hooks lint format typecheck test structure check clean
.PHONY: docker-build docker-check docker-format docker-shell secrets-baseline

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv and install all dependency groups
	$(UV) sync --all-groups

hooks: ## Install pre-commit git hooks, including the commit-msg hook
	$(UV) run pre-commit install --hook-type pre-commit --hook-type commit-msg

lint: ## Ruff lint and format check, zero errors required
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Apply ruff formatting and safe fixes
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

typecheck: ## mypy strict
	$(UV) run mypy

test: ## Run the test suite with coverage
	$(UV) run pytest

structure: ## Assert the repo matches PROJECT.md section 9
	$(UV) run pytest tests/unit/test_repo_structure.py -q --no-cov

check: lint typecheck structure test ## Everything CI runs. Use before every commit.

docker-build: ## Build the Java-enabled Linux development image
	docker build -f Dockerfile.dev -t $(DEV_IMAGE) .

docker-check: docker-build ## Run the full check inside a Linux container (see ADR-005)
	$(DOCKER_RUN) bash -c 'git config --global --add safe.directory /w && uv sync --all-groups --quiet && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest'

docker-format: docker-build ## Apply ruff fixes and formatting inside the container
	$(DOCKER_RUN) bash -c 'git config --global --add safe.directory /w && uv sync --all-groups --quiet && uv run ruff check --fix . && uv run ruff format .'

docker-shell: docker-build ## Interactive shell in the dev container
	docker run --rm -it -v "$(CURDIR):/w" -w /w -e UV_PROJECT_ENVIRONMENT=/opt/venv -v mrp-dev-venv:/opt/venv -v mrp-ivy:/root/.ivy2.5.2 $(DEV_IMAGE) bash

secrets-baseline: ## Regenerate the detect-secrets baseline
	$(DOCKER_RUN) bash -c 'git config --global --add safe.directory /w && uv sync --all-groups --quiet && uv run detect-secrets scan --exclude-files "uv.lock" > .secrets.baseline'

clean: ## Remove local caches and build artefacts
	@rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml dist build
	@rm -rf spark-warehouse metastore_db derby.log
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '.ipynb_checkpoints' -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "clean"
