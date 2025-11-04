# z2k2
API server for selected social networks

## Development

Install dependencies with `uv`:

```bash
uv sync
```

Run the development server:

```bash
uv run uvicorn app:app --reload
```

The API will be available at http://127.0.0.1:8000

- API docs: http://127.0.0.1:8000/docs
- Alternative docs: http://127.0.0.1:8000/redoc