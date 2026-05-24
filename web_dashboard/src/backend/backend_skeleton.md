# n8n_0523_2114 backend skeleton

## Overview
Backend skeleton implemented with layered architecture (API -> Application -> Domain -> Infrastructure), including:
- DTO validation
- Global error handling + unified response envelope
- Auth middleware (JWT bearer)
- Request logging middleware (with requestId/traceId)
- Rate limiting middleware (IP + user)
- Health endpoints
- Test framework (Jest + supertest) and unit tests for service methods

## Run
- Install: `npm install`
- Dev: `npm run dev`
- Build: `npm run build`
- Test: `npm test`

## Env
See `.env.example`
