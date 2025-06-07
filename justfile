init:
    python3 -m venv .venv
    python3 -m pip install --upgrade pip
    python3 -m pip --version
    pip install -r requirements.txt
    cd dispatch; python3  init_db.py

run:
    cd dispatch; python3 app.py

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
    docker run -d -p 8800:8800 dispatch:latest

docker-build:
    docker build -t dispatch:latest .

# Development commands
lint:
    python3 -m flake8 dispatch/ --exclude=venv,__pycache__,.pytest_cache

format:
    python3 -m black dispatch/ --exclude=venv

dev-setup: init
    @echo "Development environment setup complete!"
    @echo "Run 'just test' to run all tests"
    @echo "Run 'just test-coverage' to run tests with coverage"
    @echo "Run 'just run' to start the application"
