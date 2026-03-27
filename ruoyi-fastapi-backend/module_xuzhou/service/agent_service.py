import os
import base64
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List, AsyncGenerator

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.agent_dao import AgentDao
from module_xuzhou.entity.vo.agent_vo import SaveAgentMessageModel, AgentMessagePageQueryModel
from utils.log_util import logger
from utils.common_util import CamelCaseUtil


# ==================== 官方 AsyncOpenAI 客户端（支持 Qwen3-Omni-Flash 音频输入输出） ====================
client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


class AgentService:

    @classmethod
    async def stream_chat(
            cls,
            query_db: AsyncSession,
            conversation_id: str,
            user_id: Optional[str] = None,
            user_input: str = "",
            image_base64: Optional[str] = None,
            audio_base64: Optional[str] = None,
            model: str = "qwen3-omni-flash",
            system_prompt: str = "你是一个友好、专业、有帮助的AI助手，支持文字、图片、语音输入。请用自然简洁的语言回复。",
    ) -> AsyncGenerator[str, None]:
        """Qwen3-Omni-Flash 完整多模态流式聊天（支持音频输入 + 音频输出）"""
        try:
            user_content = (user_input or "").strip()
            has_image = bool(image_base64)
            has_audio = bool(audio_base64)

            if not user_content:
                if has_audio:
                    user_content = "请转录并回复我说的内容"
                elif has_image:
                    user_content = "请描述或分析这张图片"
                else:
                    user_content = "[空消息]"

            message_type = "text"
            if has_image and has_audio:
                message_type = "audio_image"
            elif has_audio:
                message_type = "audio"
            elif has_image:
                message_type = "image"

            # 保存用户消息到数据库
            await cls.save_user_message(
                query_db=query_db,
                conversation_id=conversation_id,
                user_id=user_id,
                content=user_content,
                message_type=message_type,
                metadata={
                    "has_image": has_image,
                    "has_audio": has_audio,
                    "model": model,
                }
            )
            await query_db.commit()

            # 加载历史消息（历史只保留文本）
            history_messages = await AgentDao.get_latest_messages(
                db=query_db, conversation_id=conversation_id, limit=20
            )

            # 构造 messages（系统提示 + 历史）
            messages = [{"role": "system", "content": system_prompt}]
            for msg in history_messages:
                if msg.role == "user":
                    messages.append({"role": "user", "content": msg.content or ""})
                else:
                    messages.append({"role": "assistant", "content": msg.content or ""})

            # ==================== 当前用户消息（官方多模态格式） ====================
            content_list = []
            if user_content and user_content not in ["[空消息]", "[语音消息]"]:
                content_list.append({"type": "text", "text": user_content})

            # 图片输入
            if has_image:
                if not image_base64.startswith("data:"):
                    image_base64 = f"data:image/jpeg;base64,{image_base64}"
                content_list.append({"type": "image_url", "image_url": {"url": image_base64}})

            # 音频输入（官方正确格式：input_audio）
            if has_audio:
                if not audio_base64.startswith("data:"):
                    audio_base64 = f"data:audio/webm;base64,{audio_base64}"
                content_list.append({
                    "type": "input_audio",
                    "input_audio": {
                        "data": audio_base64,
                        "format": "webm"
                    }
                })

            # 添加当前用户消息
            if content_list:
                messages.append({"role": "user", "content": content_list})
            else:
                messages.append({"role": "user", "content": user_content})

            # ==================== 官方流式调用（支持文本 + 音频输出） ====================
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                modalities=["text", "audio"],
                audio={"voice": "Cherry", "format": "wav"},  # 可改成 "Ethan" 或 "Serena"
                stream=True,
                stream_options={"include_usage": True},
                temperature=0.7,
                max_tokens=4096,
            )

            full_text = ""
            audio_base64_accum = ""

            async for chunk in stream:
                # 文字内容（实时返回给前端）
                if (chunk.choices and
                        chunk.choices[0].delta and
                        chunk.choices[0].delta.content):
                    delta_content = chunk.choices[0].delta.content
                    full_text += delta_content
                    yield delta_content

                # ==================== 音频内容修复（关键修改） ====================
                if (chunk.choices and
                        chunk.choices[0].delta and
                        hasattr(chunk.choices[0].delta, "audio") and
                        chunk.choices[0].delta.audio):

                    audio_obj = chunk.choices[0].delta.audio

                    # 兼容 dict 和对象两种情况
                    if isinstance(audio_obj, dict):
                        audio_data = audio_obj.get("data")  # dict 情况
                    else:
                        audio_data = getattr(audio_obj, "data", None)  # 对象情况

                    if audio_data:
                        audio_base64_accum += audio_data

                # 用量信息
                if hasattr(chunk, "usage") and chunk.usage:
                    yield f"[USAGE] {chunk.usage}"

            # 保存助手完整回复（文本）
            await cls.save_assistant_message(
                query_db=query_db,
                conversation_id=conversation_id,
                content=full_text.strip(),
                metadata={
                    "model": model,
                    "has_audio_output": bool(audio_base64_accum)
                }
            )
            await query_db.commit()

            # 如果生成了音频，最后 yield 音频数据
            if audio_base64_accum:
                yield f"[AUDIO]{audio_base64_accum}"

        except Exception as e:
            await query_db.rollback()
            logger.error(f"Qwen3-Omni-Flash 流式聊天异常: {str(e)}")
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