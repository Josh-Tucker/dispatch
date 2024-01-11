init:
    python3 -m venv .venv
    python3 -m pip install --upgrade pip
    python3 -m pip --version
    pip install -r requirements.txt
    cd dispatch; python3  init_db.py

run:
    cd dispatch; python3 app.py

docker-run:
    docker run -d -p 8800:8800 dispatch:latest

docker-build:
    docker build -t dispatch:latest .
