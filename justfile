init:
    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install --upgrade pip
    python3 -m pip --version
    pip install -r requirements.txt

run:
    source .venv/bin/activate
    cd dispatch; python3 app.py

# docker run:
    docker build . -t ourseses:latest

# docker build: