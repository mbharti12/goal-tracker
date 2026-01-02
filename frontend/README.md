# Goal Tracker Frontend

## Setup

```sh
npm install
```

## Development

```sh
npm run dev
```

## API Types

Generate the API client types from the backend OpenAPI spec:

```sh
npm run api:generate
```

This command expects the backend to be running at `http://localhost:8000`.

## Configuration

- `VITE_API_BASE_URL`: API base URL (defaults to `/api`, which Vite proxies to `http://localhost:8000`).
