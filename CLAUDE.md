# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This repository is a RuoYi-Vue3-FastAPI based full-stack application for an intelligent video analysis platform.

- `ruoyi-fastapi-backend/` is the FastAPI backend using async SQLAlchemy, MySQL by default with PostgreSQL support, Redis, RabbitMQ, APScheduler, and video/AI integrations.
- `ruoyi-fastapi-frontend/` is the Vue 3 + Vite frontend using Element Plus, Pinia, Vue Router, and Axios.
- The frontend dev server proxies API calls under `/dev-api` to the backend at `http://127.0.0.1:9099`.

## Common commands

Run commands from the indicated subdirectory.

### Backend

```bash
cd ruoyi-fastapi-backend
uv sync
uv run app.py --env=dev
uv run app.py --env=prod
uv run ruff check .
```

- Python version is pinned to 3.12 in `ruoyi-fastapi-backend/.python-version`.
- Backend configuration is loaded from `.env.{env}` by `config/env.py`; use `.env.dev` for local development and `.env.prod` for production.
- For PostgreSQL dependency setup instead of the default MySQL setup, the README documents:

```bash
cd ruoyi-fastapi-backend
pip3 install -r requirements-pg.txt
```

- SQL initialization files are in `ruoyi-fastapi-backend/sql/`: `ruoyi-fastapi.sql` for MySQL and `ruoyi-fastapi-pg.sql` for PostgreSQL.
- No formal backend test runner is configured in `pyproject.toml`. There are standalone scripts such as `config/test_hik.py` and `module_task/scheduler_test.py`; run only when their external dependencies/configuration are available.

### Frontend

```bash
cd ruoyi-fastapi-frontend
npm install
npm run dev
npm run build:stage
npm run build:prod
npm run preview
```

- The dev server uses port `80` from `vite.config.js`.
- `package.json` does not define `lint` or `test` scripts, and no frontend single-test command is configured.
- Frontend API base paths are defined in `.env.development`, `.env.staging`, and `.env.production`.

## Backend architecture

- `ruoyi-fastapi-backend/app.py` is the Uvicorn entrypoint. It imports `server.app` and starts Uvicorn using values from `AppConfig`.
- `ruoyi-fastapi-backend/server.py` constructs the FastAPI app, mounts sub-applications, registers middleware and exception handlers, includes routers, and defines lifespan startup/shutdown behavior.
- Startup initializes database tables, Redis system dictionaries/config, RabbitMQ queues/exchanges, APScheduler jobs, and the background inference monitor.
- Backend settings are centralized in `config/env.py`; database engine/session setup is in `config/database.py`; Redis, RabbitMQ, scheduler, SRS, and Hikvision helpers live under `config/`.
- Most backend modules follow a controller/service/dao/entity layering:
  - controllers define FastAPI routes and dependencies,
  - services coordinate business logic,
  - DAOs handle persistence,
  - `entity/do` contains SQLAlchemy models and `entity/vo` contains Pydantic request/response models.
- `module_admin/` contains the standard RuoYi system/admin functionality including login, users, roles, menus, departments, dictionaries, jobs, logs, cache, and server monitoring.
- `module_generator/` contains the code generation APIs.
- `module_xuzhou/` contains domain functionality for videos, scenes, algorithms, command callbacks, alarms, analysis, people/groups, and the AI agent.
- `module_task/` contains inference monitoring, stream checking, scheduled job examples, and monitor APIs.
- `hik_vision/` contains Hikvision/video analysis integration code and related model assets.
- Authentication differs by area: standard admin controllers generally depend on `LoginService.get_current_user` and permission checks, while Xuzhou domain controllers use `module_xuzhou.auth.unified_auth`.

## Frontend architecture

- `ruoyi-fastapi-frontend/src/main.js` creates the Vue app, installs Element Plus, Pinia, router, directives/plugins, global components, and imports `src/permission.js` for route guards.
- `src/permission.js` enforces token-based navigation, loads user info, asks the permission store to generate dynamic routes, and adds those routes to Vue Router.
- `src/store/modules/permission.js` fetches backend menu routes through `/getRouters`, maps backend component strings to Vue view components with `import.meta.glob`, normalizes selected route metadata, and merges constant/dynamic routes.
- `src/utils/request.js` is the central Axios wrapper. It sets `import.meta.env.VITE_APP_BASE_API`, attaches bearer tokens, handles duplicate-submit prevention, normalizes GET params, manages binary downloads, and converts backend response codes into UI messages.
- Frontend API wrappers live under `src/api/`, grouped by domain (`system`, `monitor`, `tool`, `xuzhou`, `binhua`, `face`). Views under `src/views/` consume these wrappers rather than calling Axios directly.
- The Xuzhou and Binhua views are domain-specific UI layers for video/camera monitoring, analysis, people/group management, alarms, clip analysis, and agent features.

## Integration notes

- Backend route prefixes and frontend API paths must stay aligned with the Vite proxy and environment base path. In development, frontend requests under `/dev-api` are rewritten to the backend root path.
- Dynamic menu route component names returned by the backend must match files under `ruoyi-fastapi-frontend/src/views/`; `src/store/modules/permission.js` also tries an `/index` suffix before falling back to the 404 view.
- Video streaming paths involve backend Xuzhou controllers/services, SRS helpers, ffmpeg process startup in the DAO layer, and frontend playback components/API wrappers.
- RabbitMQ command callbacks are initialized during backend startup and feed Xuzhou command/video status flows; check `server.py`, `config/get_rabbitmq.py`, and `module_xuzhou/controller/command_controller.py` together when changing that path.
