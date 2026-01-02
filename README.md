# Goal Tracker
An AI goal tracker with improved flexibility and LLM-based summaries.

## Quickstart

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (new terminal):

```bash
cd frontend
npm install
npm run api:generate
npm run dev
```

- `npm run api:generate` fetches `http://localhost:8000/openapi.json`, so keep the backend running.
- Vite proxies `/api` to `http://localhost:8000` in development.

## More docs

- Backend: `backend/README.md`
- Frontend: `frontend/README.md`

## Tag archiving

Archiving tags hides them from new selection while keeping historical events intact.
