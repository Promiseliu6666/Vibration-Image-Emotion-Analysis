import os
import base64
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List, AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.agent_dao import AgentDao
from module_xuzhou.entity.vo.agent_vo import SaveAgentMessageModel, AgentMessagePageQueryModel
from utils.log_util import logger
from utils.common_util import CamelCaseUtil

# ==================== 配置 ====================
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")

# ==================== LangChain Qwen 客户端 ====================
llm = ChatOpenAI(
    model="qwen-vl-plus",
    openai_api_key=os.getenv("DASHSCOPE_API_KEY"),
    openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=0.7,
    max_tokens=2048,
    streaming=True,  # 必须开启
)


class AgentService:
    """AI Agent 服务层 - 真实流式输出"""

    @classmethod
    async def process_and_store_image(cls, image_base64: str) -> Optional[str]:
        try:
            if not image_base64:
                logger.error("图片 Base64 数据为空")
                return None

            if image_base64.startswith("data:image"):
                try:
                    _, encoded = image_base64.split(",", 1)
                except ValueError:
                    encoded = image_base64
            else:
                encoded = image_base64

            file_data = base64.b64decode(encoded)

            os.makedirs(UPLOAD_DIR, exist_ok=True)
            timestamp = int(datetime.now().timestamp())
            file_name = f"{timestamp}.jpg"
            file_path = os.path.join(UPLOAD_DIR, file_name)

            with open(file_path, "wb") as f:
                f.write(file_data)

            image_url = f"/uploads/{file_name}"
            logger.info(f"图片保存成功！URL: {image_url}")
            return image_url

        except Exception as e:
            logger.error(f"处理图片失败: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    @classmethod
    async def stream_chat(
        cls,
        query_db: AsyncSession,
        conversation_id: str,
        user_id: Optional[str] = None,
        user_input: str = "",
        image_base64: Optional[str] = None,
        audio_base64: Optional[str] = None,
        model: str = "qwen-vl-plus",
        system_prompt: str = "你是一个友好、专业、有帮助的AI助手。请用简洁自然的语言回复。",
    ) -> AsyncGenerator[str, None]:
        """真实流式聊天 - 逐 token yield"""
        try:
            user_content = (user_input or "").strip()
            saved_image_url = None
            message_type = "text"

            if image_base64:
                saved_image_url = await cls.process_and_store_image(image_base64)
                if not saved_image_url:
                    raise ValueError("图片保存失败")
                message_type = "image" if not user_content else "text_image"

            if not user_content and saved_image_url:
                user_content = "请描述或分析这张图片"

            if not user_content:
                user_content = "[空消息]"

            # 保存用户消息
            await cls.save_user_message(
                query_db=query_db,
                conversation_id=conversation_id,
                user_id=user_id,
                content=user_content,
                message_type=message_type,
                image_url=saved_image_url,
                metadata={
                    "has_image": bool(image_base64),
                    "model": model,
                    "image_url": saved_image_url,
                }
            )
            await query_db.commit()

            # 加载历史
            history_messages = await AgentDao.get_latest_messages(
                db=query_db, conversation_id=conversation_id, limit=20
            )

            messages: List = [SystemMessage(content=system_prompt)]

            for msg in history_messages:
                meta = msg.metadata_json or {}
                img_url_in_history = meta.get("image_url")
                if msg.role == "user" and img_url_in_history:
                    content = msg.content or "用户发送了一张图片"
                    messages.append(HumanMessage(content=content))
                elif msg.role == "user":
                    messages.append(HumanMessage(content=msg.content or ""))
                else:
                    messages.append(AIMessage(content=msg.content or ""))

            # 当前用户消息
            if image_base64:
                if not image_base64.startswith("data:"):
                    image_base64 = f"data:image/jpeg;base64,{image_base64}"
                content_list = []
                if user_content and user_content not in ["[空消息]", "[用户发送了一张图片]"]:
                    content_list.append({"type": "text", "text": user_content})
                content_list.append({"type": "image_url", "image_url": {"url": image_base64}})
                messages.append(HumanMessage(content=content_list))
            else:
                messages.append(HumanMessage(content=user_content))

            # 真实流式调用
            current_llm = llm.with_config({"model": model}) if model != llm.model else llm

            full_content = ""
            async for chunk in current_llm.astream(messages):
                if chunk.content:
                    full_content += chunk.content
                    yield chunk.content   # 逐 token 立即发送

            # 保存完整回答
            await cls.save_assistant_message(
                query_db=query_db,
                conversation_id=conversation_id,
                content=full_content.strip(),
                metadata={"model": model}
            )
            await query_db.commit()

        except Exception as e:
            await query_db.rollback()
            logger.error(f"流式聊天异常: {str(e)}")
            logger.error(traceback.format_exc())
            yield f"[ERROR] {str(e)}"

    @classmethod
    async def save_user_message(
        cls,
        query_db: AsyncSession,
        conversation_id: str,
        user_id: Optional[str],
        content: str,
        message_type: str = "text",
        image_url: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        if not conversation_id or not conversation_id.strip():
            conversation_id = f"conv_{int(datetime.now().timestamp())}"

        msg = SaveAgentMessageModel(
            conversation_id=conversation_id.strip(),
            user_id=user_id,
            role="user",
            content=content or "[空消息]",
            metadata_json={
                "type": message_type,
                "image_url": image_url,
                **(metadata or {})
            }
        )
        await AgentDao.save_message_dao(query_db, msg)

    @classmethod
    async def save_assistant_message(
        cls,
        query_db: AsyncSession,
        conversation_id: str,
        content: str,
        metadata: Optional[Dict] = None,
    ):
        msg = SaveAgentMessageModel(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            metadata_json=metadata or {}
        )
        await AgentDao.save_message_dao(query_db, msg)

    @classmethod
    async def get_chat_history(
        cls, query_db: AsyncSession, conversation_id: str, limit: int = 50
    ):
        messages = await AgentDao.get_messages_by_conversation(
            query_db, conversation_id, limit=limit
        )
        return [CamelCaseUtil.transform_result(m) for m in messages]

    @classmethod
    async def get_agent_message_list_services(
        cls,
        query_db: AsyncSession,
        query_object: AgentMessagePageQueryModel,
        is_page: bool = True,
    ):
        return await AgentDao.get_message_list(
            db=query_db, query_object=query_object, is_page=is_page
        )