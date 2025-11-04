# z2k2
API server for selected social networks

## Development

Install dependencies with `uv`:

```bash
uv sync
```

Run the development server (with auto-reload):

```bash
uv run fastapi dev app.py
```

Run in production mode locally:

```bash
uv run fastapi run app.py
```

The API will be available at http://127.0.0.1:8000

- API docs: http://127.0.0.1:8000/docs
- Alternative docs: http://127.0.0.1:8000/redoc

## Requirements

- Python 3.13+
- Twitter OAuth sessions in `sessions.jsonl` (required for API access)
