# manager_api (FastAPI)

This sub-application embeds `manager_api` into `ruoyi-fastapi-backend` as a FastAPI app.

## Mount path

By default it is mounted at:

- `/manager-api`

With the backend `APP_ROOT_PATH=/dev-api`, final URLs are:

- `/dev-api/manager-api/doc.html`
- `/dev-api/manager-api/v3/api-docs`
- `/dev-api/manager-api/login`
- `/dev-api/manager-api/getInfo`
- `/dev-api/manager-api/getRouters`
- `/dev-api/manager-api/xiaozhi/*`

## Environment variables

- `MANAGER_API_MOUNT_PREFIX` (default: `/manager-api`)
- `MANAGER_API_XIAOZHI_PREFIX` (default: `/xiaozhi`)
- `MANAGER_API_RUOYI_PREFIX` (default: empty)
- `MANAGER_API_DATABASE_URL` (default: `sqlite:///.../ruoyi-fastapi-backend/vf_admin/manager_api.db`)
- `MANAGER_API_JWT_SECRET` (default: fallback to backend `JwtConfig.jwt_secret_key`)
- `MANAGER_API_JWT_ALGORITHM` (default: fallback to backend `JwtConfig.jwt_algorithm`)
- `MANAGER_API_JWT_EXPIRE_SECONDS` (default: `43200`)
- `MANAGER_API_SERVER_SECRET` (default: `manager-api-secret`)
- `MANAGER_API_CORS_ORIGINS` (default: `*`)

## Seed data

On first startup, if no `sys_user` data exists in this database, it seeds:

- username: `admin`
- password: `admin123`
