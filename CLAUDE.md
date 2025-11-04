# Claude Code Instructions

## Twitter/X API Implementation

**IMPORTANT**: When implementing Twitter/X API related code, especially parsing results from Twitter/X GraphQL API:

1. **Always consult https://github.com/zedeus/nitter first** instead of guessing
2. Study nitter's actual implementation in the following files:
   - `src/parser.nim` - Tweet and timeline parsing
   - `src/api.nim` - GraphQL API calls
   - `src/apiutils.nim` - Authentication and headers
   - `src/consts.nim` - API endpoints and constants
   - `src/experimental/parser/graphql.nim` - GraphQL parsing helpers

3. When encountering issues:
   - Add debug logging to see actual response structure
   - Compare with nitter's implementation
   - Don't assume structure based on documentation - Twitter's API differs from docs

## General Guidelines

- This codebase is based on nitter's reverse-engineered Twitter GraphQL API implementation
- Session management uses OAuth tokens from `sessions.jsonl` with round-robin rotation
- All Twitter API code should match nitter's proven patterns

## Documentation

**README.md**: Do NOT include Docker or CI/CD explanations in README.md. Keep the README focused on:
- Development setup
- Running the application locally
- Basic requirements

Docker, CI/CD, and deployment information should be self-explanatory from the Dockerfile and workflow files.

## Code Organization

**Internal vs Public API**: All methods, functions, and classes in the `z2k2/` module that are NOT used in `app.py` must be prefixed with `_` to indicate they are internal implementation details.

Public API (used in `app.py`):
- `TwitterClient`, `TwitterAPIError`, `RateLimitError`
- `parse_user_from_graphql()`, `parse_profile_from_graphql()`
- `User`, `Profile`, `Tweet`, `Timeline`, and related model classes
- `SessionManager` and its public method: `get_session()`
- `SqliteCache` (initialized in app.py and set to `twitter_client._cache`)

All other functions, methods, and classes should be prefixed with `_` to mark them as internal.

## Code Style

**No Default Parameters in Constructors**: Constructors (`__init__` methods) must NOT have default parameter values. All parameters must be explicitly provided when instantiating classes.

**Cache Key Naming Convention**: When using the `@cached` decorator, cache keys must follow this pattern:
- Format: `{module}.{function_name}.{param1}.{param2}...`
- Start with the module/class name (e.g., `twitter_client`)
- Include the full method/function name
- Include all relevant parameters separated by dots
- Use descriptive default values (e.g., `first` instead of empty string)

Example:
```python
@cached(lambda: _cache, lambda username: f"twitter_client.get_user_by_screen_name.{username}")
@cached(lambda: _cache, lambda user_id, cursor=None: f"twitter_client.get_user_tweets.{user_id}.{cursor or 'first'}")
```

Note: The cache must be passed as a lambda (`lambda: _cache`) to defer evaluation until runtime, not decoration time.
