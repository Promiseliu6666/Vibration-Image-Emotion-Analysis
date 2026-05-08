import base64
import json
import traceback
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.dao.agent_dao import AgentDao
from module_xuzhou.entity.vo.agent_vo import AgentMessagePageQueryModel
from module_xuzhou.service.agent_service import AgentService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

agent_controller = APIRouter(
    prefix="/agent",
    dependencies=[Depends(unified_auth)],
)


@agent_controller.post("/chat", summary="AI Agent streaming chat")
@integration_log(
    title="AI Agent Chat",
    system_name="Xuzhou Personnel Management System",
    business_type=BusinessType.OTHER,
)
async def agent_chat(
    request: Request,
    conversation_id: str = Form(..., description="Conversation ID"),
    user_id: Optional[str] = Form(None, description="User ID"),
    message: str = Form("", description="User text input"),
    model: str = Form("qwen3-omni-flash", description="Model name"),
    image: Optional[UploadFile] = File(None, description="Image file"),
    audio: Optional[UploadFile] = File(None, description="Audio file"),
    query_db: AsyncSession = Depends(get_db),
):
    try:
        if not conversation_id or not conversation_id.strip():
            conversation_id = f"conv_{int(datetime.now().timestamp())}"
        conversation_id = conversation_id.strip()

        image_base64 = None
        if image:
            image_content = await image.read()
            image_base64 = base64.b64encode(image_content).decode("utf-8")

        audio_base64 = None
        if audio:
            audio_content = await audio.read()
            audio_base64 = base64.b64encode(audio_content).decode("utf-8")

        async def event_generator():
            yield (
                "data: "
                + json.dumps(
                    {"type": "meta", "conversation_id": conversation_id},
                    ensure_ascii=False,
                )
                + "\n\n"
            )

            async for event in AgentService.stream_chat(
                query_db=query_db,
                conversation_id=conversation_id,
                user_id=user_id,
                user_input=message,
                image_base64=image_base64,
                audio_base64=audio_base64,
                model=model,
            ):
                payload = event if isinstance(event, dict) else {"type": "delta", "content": str(event)}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        await query_db.rollback()
        logger.error(f"Agent chat failed: {str(e)}")
        logger.error(traceback.format_exc())
        payload = json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)
        return StreamingResponse(
            iter([f"data: {payload}\n\n", "data: [DONE]\n\n"]),
            media_type="text/event-stream",
        )


@agent_controller.get("/history/{conversation_id}", summary="Get conversation history")
@integration_log(
    title="Get Agent Conversation History",
    system_name="Xuzhou Personnel Management System",
    business_type=BusinessType.OTHER,
)
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
        logger.error(f"Get history failed: {str(e)}")
        return ResponseUtil.error(msg=f"Get history failed: {str(e)}")


@agent_controller.get("/conversations", summary="Get conversation summaries")
@integration_log(
    title="Get Agent Conversation List",
    system_name="Xuzhou Personnel Management System",
    business_type=BusinessType.OTHER,
)
async def get_agent_conversations(
    request: Request,
    user_id: Optional[str] = None,
    limit: int = 20,
    query_db: AsyncSession = Depends(get_db),
):
    try:
        safe_limit = max(1, min(limit, 100))
        conversations = await AgentService.get_conversation_list(
            query_db=query_db,
            user_id=user_id,
            limit=safe_limit,
        )
        return ResponseUtil.success(data={"conversations": conversations})
    except Exception as e:
        logger.error(f"Get conversation list failed: {str(e)}")
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f"Get conversation list failed: {str(e)}")


@agent_controller.get("/list", response_model=PageResponseModel, summary="Paged query for agent messages")
@integration_log(
    title="Get Agent Message List",
    system_name="Xuzhou Personnel Management System",
    business_type=BusinessType.OTHER,
)
async def get_agent_message_list(
    request: Request,
    page_num: int = 1,
    page_size: int = 20,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    role: Optional[str] = None,
    include_deleted: bool = False,
    order_by: Optional[str] = "created_time",
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
        logger.error(f"Get agent message list failed: {str(e)}")
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f"Query failed: {str(e)}")


@agent_controller.delete("/conversation/{conversation_id}", summary="Soft delete conversation")
@integration_log(
    title="Delete Agent Conversation",
    system_name="Xuzhou Personnel Management System",
    business_type=BusinessType.DELETE,
)
async def delete_conversation(
    request: Request,
    conversation_id: str,
    query_db: AsyncSession = Depends(get_db),
):
    try:
        await AgentDao.soft_delete_by_conversation(query_db, conversation_id)
        await query_db.commit()
        return ResponseUtil.success(msg="Conversation deleted successfully")
    except Exception as e:
        await query_db.rollback()
        logger.error(f"Delete conversation failed: {str(e)}")
        return ResponseUtil.error(msg=f"Delete failed: {str(e)}")
