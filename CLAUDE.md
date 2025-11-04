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
