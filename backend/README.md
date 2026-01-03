# Goal Tracker Backend

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

## Configuration

- `DB_PATH`: SQLite file path (default `backend/data/app.db`).
- `DB_URL`: full SQLAlchemy URL (overrides `DB_PATH`).
- `LOG_LEVEL`: logging level (default `INFO`).
- `OLLAMA_MODEL`: model name for summaries (default `llama3.2:1b`).
- `OLLAMA_BASE_URL`: Ollama server URL (default `http://localhost:11434`).

## Ollama (Local LLM)

Install Ollama and pull the default model:

```bash
brew install ollama
ollama serve
ollama pull llama3.2:1b
```

Set a different model with `OLLAMA_MODEL`, for example:

```bash
export OLLAMA_MODEL=llama3.2:1b
```

Point at a non-default Ollama host with `OLLAMA_BASE_URL`, for example:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
```

## Notes
- SQLite database file defaults to `backend/data/app.db`.
- CORS is enabled for `http://localhost:5173`.
- Archived tags are hidden from new selection but keep historical tag events intact.
