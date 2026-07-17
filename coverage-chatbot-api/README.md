# coverage-chatbot-api

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload
```

## Health check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```
