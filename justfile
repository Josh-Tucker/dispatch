init:
    python3 -m venv .venv
    python3 -m pip install --upgrade pip
    python3 -m pip --version
    pip install -r requirements-all.txt
    cd dispatch; python3  init_db.py

run:
    cd dispatch; DEBUG=true python3 app.py

# Test commands
test:
    python3 -m pytest tests/ -v

test-unit:
    python3 -m pytest tests/ -v -m unit

test-integration:
    python3 -m pytest tests/ -v -m integration

test-coverage:
    python3 -m pytest tests/ --cov=dispatch --cov-report=term-missing --cov-report=html

test-fast:
    python3 -m pytest tests/ -v -x --disable-warnings



test-watch:
    python3 -m pytest tests/ -f

test-debug:
    python3 -m pytest tests/ -v -s --tb=long

test-specific file="":
    python3 -m pytest tests/{{file}} -v

test-clean:
    rm -rf .pytest_cache htmlcov .coverage

# Docker commands
docker-run:
    docker run -d -p 5000:5000 dispatch:latest

docker-build:
    docker build -t dispatch:latest .

# Development commands
lint:
    python3 -m flake8 dispatch/ --exclude=venv,__pycache__,.pytest_cache

format:
    python3 -m black dispatch/ --exclude=venv

# Ruff commands (modern linting and formatting)
ruff-check:
    python3 -m ruff check dispatch/

ruff-fix:
    python3 -m ruff check --fix dispatch/

ruff-format:
    python3 -m ruff format dispatch/

# Combined code quality commands
quality-check: ruff-check
    @echo "✅ Code quality check complete"

quality-fix: ruff-fix
    @echo "🔧 Auto-fixable issues resolved"

quality-format: ruff-format
    @echo "🎨 Code formatting applied"

quality-all: quality-fix quality-format
    @echo "🚀 All code quality improvements applied"

# Requirements management
install-prod:
    pip install -r requirements.txt

install-dev:
    pip install -r requirements-dev.txt

install-all:
    pip install -r requirements-all.txt

update-requirements:
    pip freeze > requirements-current.txt
    @echo "Current environment frozen to requirements-current.txt"
    @echo "Review and update requirements.txt and requirements-dev.txt as needed"

dev-setup: init
    @echo "Development environment setup complete!"
    @echo "Run 'just test' to run all tests"
    @echo "Run 'just test-coverage' to run tests with coverage"
    @echo "Run 'just run' to start the application"
    @echo ""
    @echo "Requirements commands:"
    @echo "  just install-prod     - Install production dependencies only"
    @echo "  just install-dev      - Install development dependencies only"
    @echo "  just install-all      - Install all dependencies"
    @echo ""
    @echo "Code quality commands:"
    @echo "  just lint             - Run flake8 linting"
    @echo "  just format           - Format code with black"
    @echo "  just ruff-check       - Check code with ruff"
    @echo "  just ruff-fix         - Fix auto-fixable ruff issues"
    @echo "  just ruff-format      - Format code with ruff"
