from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from config.get_db import get_db
from module_admin.service.login_service import LoginService, oauth2_scheme

X_API_TOKEN = APIKeyHeader(name='X-API-Token', auto_error=False)


async def unified_auth(
    request: Request,
    api_token: str = Depends(X_API_TOKEN),
    jwt_token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    try:
        if api_token:
            # 尝试API Token认证
            redis_key = f'api_token_key:1'
            token_info = await request.app.state.redis.hgetall(redis_key)

            if token_info and token_info.get('token') == api_token:
                return {'user_id': 1}
            else:
                raise HTTPException(status_code=401, detail='Invalid Token')
        elif jwt_token:
            return await LoginService.get_current_user(request, jwt_token, db)
        else:
            raise HTTPException(status_code=401, detail='No Token')

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
