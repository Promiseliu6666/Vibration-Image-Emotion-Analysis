import os
import traceback
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.agent_dao import AgentDao
from module_xuzhou.entity.vo.agent_vo import AgentMessagePageQueryModel, SaveAgentMessageModel
from utils.common_util import CamelCaseUtil
from utils.log_util import logger

client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


class AgentService:
    DEFAULT_SYSTEM_PROMPT = (
        "你是一个专业且简洁的 AI 助手。"
        "回答要准确、结构清晰、避免冗余。"
        "如果上下文不足，请明确指出并给出下一步建议。"
    )
    CONTEXT_MAX_MESSAGES = 24
    CONTEXT_MAX_CHARS = 12000
    MESSAGE_CONTENT_MAX_CHARS = 1600
    PLACEHOLDERS = {
        "[空消息]",
        "[语音消息]",
        "[empty_message]",
        "[voice_message]",
    }

    @classmethod
    def _clean_text(cls, text: Optional[str]) -> str:
        if text is None:
            return ""
        return str(text).replace("\r\n", "\n").strip()

    @classmethod
    def _clip_preview(cls, text: str, limit: int = 80) -> str:
        if not text:
            return ""
        normalized = " ".join(text.split())
        return normalized if len(normalized) <= limit else f"{normalized[:limit]}..."

    @classmethod
    def _build_conversation_title(cls, title_hint: str, conversation_id: str) -> str:
        hint = cls._clip_preview(title_hint, 28)
        if hint:
            return hint
        return f"会话 {conversation_id[-6:]}" if conversation_id else "新会话"

    @classmethod
    def _normalize_role(cls, role: str) -> str:
        if role in {"assistant", "system", "tool"}:
            return role
        return "user"

    @classmethod
    def _normalize_history_message_content(cls, history_message: Any) -> str:
        content = cls._clean_text(history_message.content)
        metadata = history_message.metadata_json or {}
        if not isinstance(metadata, dict):
            metadata = {}

        hints = []
        if metadata.get("has_image"):
            hints.append("[用户曾发送图片]")
        if metadata.get("has_audio"):
            hints.append("[用户曾发送语音]")

        if hints:
            if content:
                content = f"{content}\n{' '.join(hints)}"
            else:
                content = " ".join(hints)

        if len(content) > cls.MESSAGE_CONTENT_MAX_CHARS:
            content = content[: cls.MESSAGE_CONTENT_MAX_CHARS]
        return content

    @classmethod
    def _build_context_messages(
        cls,
        history_messages: list[Any],
        system_prompt: str,
    ) -> list[dict]:
        selected = history_messages[-cls.CONTEXT_MAX_MESSAGES :]
        context_messages: list[dict] = []
        total_chars = 0

        for item in reversed(selected):
            role = cls._normalize_role(getattr(item, "role", "user"))
            content = cls._normalize_history_message_content(item)
            if not content:
                continue

            next_total = total_chars + len(content)
            if next_total > cls.CONTEXT_MAX_CHARS:
                if not context_messages:
                    content = content[: cls.CONTEXT_MAX_CHARS]
                else:
                    break

            context_messages.append({"role": role, "content": content})
            total_chars += len(content)

        context_messages.reverse()
        return [{"role": "system", "content": system_prompt}] + context_messages

    @classmethod
    def _extract_delta_text(cls, delta: Any) -> str:
        if not delta:
            return ""

        if isinstance(delta, dict):
            raw_content = delta.get("content")
        else:
            raw_content = getattr(delta, "content", None)

        if not raw_content:
            return ""
        if isinstance(raw_content, str):
            return raw_content
        if isinstance(raw_content, list):
            parts: list[str] = []
            for item in raw_content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(getattr(item, "text", "") or getattr(item, "content", "") or ""))
            return "".join(parts)
        return str(raw_content)

    @classmethod
    def _extract_reasoning_text(cls, delta: Any) -> str:
        if not delta:
            return ""

        if isinstance(delta, dict):
            raw_reasoning = delta.get("reasoning") or delta.get("reasoning_content")
        else:
            raw_reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)

        if not raw_reasoning:
            return ""
        if isinstance(raw_reasoning, str):
            return raw_reasoning
        if isinstance(raw_reasoning, list):
            parts: list[str] = []
            for item in raw_reasoning:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(getattr(item, "text", "") or getattr(item, "content", "") or ""))
            return "".join(parts)
        return str(raw_reasoning)

    @classmethod
    def _extract_usage_metrics(cls, usage: Any) -> dict[str, Any]:
        if not usage:
            return {}
        if isinstance(usage, dict):
            return usage

        if hasattr(usage, "to_dict"):
            usage_dict = usage.to_dict()
            if isinstance(usage_dict, dict):
                return usage_dict

        if hasattr(usage, "model_dump"):
            usage_dict = usage.model_dump()
            if isinstance(usage_dict, dict):
                return usage_dict

        return {}

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
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> AsyncGenerator[dict, None]:
        try:
            conversation_id = (conversation_id or "").strip()
            if not conversation_id:
                conversation_id = f"conv_{int(datetime.now().timestamp())}"

            user_content = cls._clean_text(user_input)
            has_image = bool(image_base64)
            has_audio = bool(audio_base64)

            if not user_content:
                if has_image and has_audio:
                    user_content = "请结合图片和语音内容给出回答。"
                elif has_audio:
                    user_content = "请识别语音内容并给出回答。"
                elif has_image:
                    user_content = "请描述并分析这张图片。"
                else:
                    user_content = "[empty_message]"

            if has_image and has_audio:
                message_type = "audio_image"
            elif has_audio:
                message_type = "audio"
            elif has_image:
                message_type = "image"
            else:
                message_type = "text"

            current_user_message_id = await cls.save_user_message(
                query_db=query_db,
                conversation_id=conversation_id,
                user_id=user_id,
                content=user_content,
                message_type=message_type,
                metadata={
                    "has_image": has_image,
                    "has_audio": has_audio,
                    "model": model,
                },
            )
            await query_db.commit()

            history_messages = await AgentDao.get_latest_messages(
                db=query_db,
                conversation_id=conversation_id,
                limit=cls.CONTEXT_MAX_MESSAGES + 8,
            )
            history_context = [msg for msg in history_messages if msg.id != current_user_message_id]
            messages = cls._build_context_messages(history_context, system_prompt)

            current_message_content: list[dict] = []
            if user_content and user_content not in cls.PLACEHOLDERS:
                current_message_content.append({"type": "text", "text": user_content})

            if has_image:
                image_data = image_base64 or ""
                if image_data and not image_data.startswith("data:"):
                    image_data = f"data:image/jpeg;base64,{image_data}"
                if image_data:
                    current_message_content.append(
                        {"type": "image_url", "image_url": {"url": image_data}}
                    )

            if has_audio:
                audio_data = audio_base64 or ""
                if audio_data and not audio_data.startswith("data:"):
                    audio_data = f"data:audio/webm;base64,{audio_data}"
                if audio_data:
                    current_message_content.append(
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_data,
                                "format": "webm",
                            },
                        }
                    )

            if current_message_content:
                if len(current_message_content) == 1 and current_message_content[0]["type"] == "text":
                    messages.append({"role": "user", "content": current_message_content[0]["text"]})
                else:
                    messages.append({"role": "user", "content": current_message_content})
            else:
                messages.append({"role": "user", "content": user_content})

            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                modalities=["text", "audio"],
                audio={"voice": "Cherry", "format": "wav"},
                stream=True,
                stream_options={"include_usage": True},
                temperature=0.7,
                max_tokens=4096,
            )

            full_text = ""
            audio_base64_accum = ""
            full_reasoning = ""
            usage_metrics: dict[str, Any] = {}
            run_id = f"run_{uuid.uuid4().hex[:24]}"

            yield {"type": "run_info", "run_id": run_id, "model": model}

            async for chunk in stream:
                delta = None
                if getattr(chunk, "choices", None):
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)

                reasoning_content = cls._extract_reasoning_text(delta)
                if reasoning_content:
                    full_reasoning += reasoning_content
                    yield {"type": "reasoning", "content": reasoning_content}

                delta_content = cls._extract_delta_text(delta)
                if delta_content:
                    full_text += delta_content
                    yield {"type": "content", "content": delta_content}

                if delta and hasattr(delta, "audio") and delta.audio:
                    audio_obj = delta.audio
                    if isinstance(audio_obj, dict):
                        audio_data = audio_obj.get("data")
                    else:
                        audio_data = getattr(audio_obj, "data", None)
                    if audio_data:
                        audio_base64_accum += audio_data

                if hasattr(chunk, "usage") and chunk.usage:
                    usage_metrics = cls._extract_usage_metrics(chunk.usage)

            if usage_metrics:
                yield {"type": "metrics", "metrics": CamelCaseUtil.transform_result(usage_metrics)}

            await cls.save_assistant_message(
                query_db=query_db,
                conversation_id=conversation_id,
                content=(full_text or "").strip(),
                metadata={
                    "model": model,
                    "run_id": run_id,
                    "reasoning_content": full_reasoning,
                    "has_audio_output": bool(audio_base64_accum),
                    "context_message_count": len(messages),
                    "usage": usage_metrics,
                },
            )
            await query_db.commit()

            if audio_base64_accum:
                yield {"type": "audio", "content": audio_base64_accum}

        except Exception as e:
            await query_db.rollback()
            logger.error(f"stream_chat failed: {str(e)}")
            logger.error(traceback.format_exc())
            yield {"type": "error", "content": str(e)}

    @classmethod
    async def save_user_message(
        cls,
        query_db: AsyncSession,
        conversation_id: str,
        user_id: Optional[str],
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict] = None,
    ) -> int:
        if not conversation_id or not conversation_id.strip():
            conversation_id = f"conv_{int(datetime.now().timestamp())}"

        msg = SaveAgentMessageModel(
            conversation_id=conversation_id.strip(),
            user_id=user_id,
            role="user",
            content=content or "[empty_message]",
            metadata_json={
                "type": message_type,
                **(metadata or {}),
            },
        )
        return await AgentDao.save_message_dao(query_db, msg)

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
            content=content or "",
            metadata_json=metadata or {},
        )
        await AgentDao.save_message_dao(query_db, msg)

    @classmethod
    async def get_chat_history(
        cls,
        query_db: AsyncSession,
        conversation_id: str,
        limit: int = 50,
    ):
        messages = await AgentDao.get_messages_by_conversation(
            query_db,
            conversation_id,
            limit=limit,
        )
        return [CamelCaseUtil.transform_result(m) for m in messages]

    @classmethod
    async def get_conversation_list(
        cls,
        query_db: AsyncSession,
        user_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        summaries = await AgentDao.get_conversation_summaries(
            db=query_db,
            user_id=user_id,
            limit=limit,
        )

        result: list[dict] = []
        for item in summaries:
            last_message = cls._clip_preview(cls._clean_text(item.get("last_message")), 120)
            title = cls._build_conversation_title(
                cls._clean_text(item.get("title_hint")) or last_message,
                item.get("conversation_id") or "",
            )
            result.append(
                {
                    "conversation_id": item.get("conversation_id"),
                    "title": title,
                    "last_message": last_message,
                    "message_count": int(item.get("message_count") or 0),
                    "created_time": item.get("created_time"),
                    "last_active_time": item.get("last_active_time"),
                }
            )
        return result

    @classmethod
    async def get_agent_message_list_services(
        cls,
        query_db: AsyncSession,
        query_object: AgentMessagePageQueryModel,
        is_page: bool = True,
    ):
        return await AgentDao.get_message_list(
            db=query_db,
            query_object=query_object,
            is_page=is_page,
        )
