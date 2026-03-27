import base64
import traceback
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.dao.agent_dao import AgentDao
from module_xuzhou.service.agent_service import AgentService
from module_xuzhou.entity.vo.agent_vo import AgentMessagePageQueryModel
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

agent_controller = APIRouter(
    prefix="/agent",
    dependencies=[Depends(unified_auth)]   # 测试时可先注释
)


@agent_controller.post("/chat", summary="AI Agent 对话（Qwen3-Omni-Flash 全模态流式）")
@integration_log(
    title="AI Agent 对话",
    system_name="徐州人员管理系统",
    business_type=BusinessType.OTHER,
)
async def agent_chat(
    request: Request,
    conversation_id: str = Form(..., description="会话ID"),
    user_id: Optional[str] = Form(None, description="用户ID"),
    message: str = Form("", description="用户输入文字"),
    model: str = Form("qwen3-omni-flash", description="模型名称"),
    image: Optional[UploadFile] = File(None, description="图片文件"),
    audio: Optional[UploadFile] = File(None, description="语音文件"),
    query_db: AsyncSession = Depends(get_db),
):
    try:
        if not conversation_id or conversation_id.strip() == "":
            conversation_id = f"conv_{int(datetime.now().timestamp())}"

        image_base64 = None
        if image:
            content = await image.read()
            image_base64 = base64.b64encode(content).decode("utf-8")

        audio_base64 = None
        if audio:
            content = await audio.read()
            audio_base64 = base64.b64encode(content).decode("utf-8")

        async def event_generator():
            async for token in AgentService.stream_chat(
                query_db=query_db,
                conversation_id=conversation_id.strip(),
                user_id=user_id,
                user_input=message,
                image_base64=image_base64,
                audio_base64=audio_base64,
                model=model,
            ):
                yield f"data: {token}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        await query_db.rollback()
        logger.error(f"Agent 对话失败: {str(e)}")
        logger.error(traceback.format_exc())
        return StreamingResponse(
            iter([f"data: [ERROR] {str(e)}\n\n"]),
            media_type="text/event-stream"
        )


@agent_controller.get("/history/{conversation_id}", summary="获取会话历史消息")
@integration_log(title="获取 Agent 会话历史", system_name="徐州人员管理系统", business_type=BusinessType.OTHER)
async def get_agent_history(
    request: Request,
    conversation_id: str,
    limit: int = 50,
    query_db: AsyncSession = Depends(get_db),
):
    try:
        history = await AgentService.get_chat_history(query_db, conversation_id, limit)
        return ResponseUtil.success(data={"history": history})
    except Exception as e:
        logger.error(f"获取历史消息失败: {str(e)}")
        return ResponseUtil.error(msg=f"获取历史失败: {str(e)}")


@agent_controller.get('/list', response_model=PageResponseModel, summary='分页查询 Agent 消息记录')
@integration_log(title='查询 Agent 消息列表', system_name='徐州人员管理系统', business_type=BusinessType.OTHER)
async def get_agent_message_list(
    request: Request,
    page_num: int = 1,
    page_size: int = 20,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    role: Optional[str] = None,
    include_deleted: bool = False,
    order_by: Optional[str] = 'created_time',
    query_db: AsyncSession = Depends(get_db),
):
    try:
        query_object = AgentMessagePageQueryModel(
            page_num=page_num,
            page_size=page_size,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_id=agent_id,
            role=role,
            include_deleted=include_deleted,
            order_by=order_by,
        )
        result = await AgentService.get_agent_message_list_services(
            query_db, query_object, is_page=True
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        await query_db.rollback()
        logger.error(f"查询 Agent 消息列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f"查询失败: {str(e)}")


@agent_controller.delete("/conversation/{conversation_id}", summary="软删除整个会话")
@integration_log(title="删除 Agent 会话", system_name="徐州人员管理系统", business_type=BusinessType.DELETE)
async def delete_conversation(
    request: Request,
    conversation_id: str,
    query_db: AsyncSession = Depends(get_db),
):
    try:
        await AgentDao.soft_delete_by_conversation(query_db, conversation_id)
        await query_db.commit()
        return ResponseUtil.success(msg="会话删除成功")
    except Exception as e:
        await query_db.rollback()
        logger.error(f"删除会话失败: {str(e)}")
        return ResponseUtil.error(msg=f"删除失败: {str(e)}")