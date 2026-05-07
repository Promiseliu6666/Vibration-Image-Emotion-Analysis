# agent_dao.py
from datetime import datetime
from typing import Sequence, Optional

from sqlalchemy import select, update, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.entity.do.agent_do import AgentMessage   # ← 你前面创建的 DO 文件
from module_xuzhou.entity.vo.agent_vo import (
    AgentMessagePageQueryModel,
    SaveAgentMessageModel
)
from utils.page_util import PageUtil


class AgentDao:
    """AI Agent 消息记录 DAO"""

    @classmethod
    async def get_message_by_id(cls, db: AsyncSession, message_id: int) -> AgentMessage | None:
        """根据消息ID获取单条记录"""
        return (await db.execute(
            select(AgentMessage).where(AgentMessage.id == message_id)
        )).scalars().first()

    @classmethod
    async def get_messages_by_conversation(
        cls,
        db: AsyncSession,
        conversation_id: str,
        limit: int = 100,
        include_deleted: bool = False
    ) -> Sequence[AgentMessage]:
        """获取某个会话的全部消息（按时间正序）"""
        query = select(AgentMessage).where(
            AgentMessage.conversation_id == conversation_id
        )

        if not include_deleted:
            query = query.where(AgentMessage.is_deleted == False)

        query = query.order_by(AgentMessage.created_time.asc()).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    @classmethod
    async def get_latest_messages(
        cls,
        db: AsyncSession,
        conversation_id: str,
        limit: int = 20,
        include_deleted: bool = False
    ) -> Sequence[AgentMessage]:
        """获取某个会话最新的N条消息（常用于构造 prompt 上下文）"""
        query = select(AgentMessage).where(
            AgentMessage.conversation_id == conversation_id
        )

        if not include_deleted:
            query = query.where(AgentMessage.is_deleted == False)

        query = query.order_by(desc(AgentMessage.created_time)).limit(limit)

        result = await db.execute(query)
        # 因为要正序返回，所以反转一下
        return list(reversed(result.scalars().all()))

    @classmethod
    async def get_message_list(
        cls,
        db: AsyncSession,
        query_object: AgentMessagePageQueryModel,
        is_page: bool = True
    ):
        """分页查询 Agent 消息（支持多条件筛选）"""
        query = select(AgentMessage).where(
            AgentMessage.conversation_id == query_object.conversation_id if query_object.conversation_id else True,
            AgentMessage.user_id == query_object.user_id if query_object.user_id else True,
            AgentMessage.agent_id == query_object.agent_id if query_object.agent_id else True,
            AgentMessage.role == query_object.role if query_object.role else True,
            True if query_object.include_deleted else AgentMessage.is_deleted == False,
        ).order_by(AgentMessage.created_time.desc())

        return await PageUtil.paginate(
            db, query, query_object.page_num, query_object.page_size, is_page
        )

    @classmethod
    async def get_conversation_summaries(
        cls,
        db: AsyncSession,
        user_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get conversation summaries sorted by latest activity."""
        summary_query = (
            select(
                AgentMessage.conversation_id.label("conversation_id"),
                func.max(AgentMessage.created_time).label("last_active_time"),
                func.min(AgentMessage.created_time).label("created_time"),
                func.count(AgentMessage.id).label("message_count"),
            )
            .where(AgentMessage.is_deleted == False)
        )

        if user_id:
            summary_query = summary_query.where(AgentMessage.user_id == user_id)

        summary_query = (
            summary_query.group_by(AgentMessage.conversation_id)
            .order_by(desc("last_active_time"))
            .limit(limit)
        )
        summary_rows = (await db.execute(summary_query)).all()
        if not summary_rows:
            return []

        conversation_ids = [row.conversation_id for row in summary_rows]

        detail_query = (
            select(
                AgentMessage.conversation_id,
                AgentMessage.role,
                AgentMessage.content,
                AgentMessage.created_time,
            )
            .where(
                AgentMessage.conversation_id.in_(conversation_ids),
                AgentMessage.is_deleted == False,
            )
            .order_by(desc(AgentMessage.created_time))
        )
        if user_id:
            detail_query = detail_query.where(AgentMessage.user_id == user_id)

        detail_rows = (await db.execute(detail_query)).all()

        last_message_by_conv: dict[str, str] = {}
        title_hint_by_conv: dict[str, str] = {}

        for row in detail_rows:
            conv_id = row.conversation_id
            content = (row.content or "").strip()

            if conv_id not in last_message_by_conv:
                last_message_by_conv[conv_id] = content

            if row.role == "user" and conv_id not in title_hint_by_conv and content:
                title_hint_by_conv[conv_id] = content

        result: list[dict] = []
        for row in summary_rows:
            result.append(
                {
                    "conversation_id": row.conversation_id,
                    "created_time": row.created_time,
                    "last_active_time": row.last_active_time,
                    "message_count": int(row.message_count or 0),
                    "last_message": last_message_by_conv.get(row.conversation_id, ""),
                    "title_hint": title_hint_by_conv.get(row.conversation_id, ""),
                }
            )
        return result

    @classmethod
    async def save_message_dao(
        cls,
        db: AsyncSession,
        message: SaveAgentMessageModel
    ) -> int:
        """保存一条 Agent 消息"""
        db_message = AgentMessage(
            conversation_id=message.conversation_id,
            user_id=message.user_id,
            agent_id=message.agent_id,
            role=message.role,
            content=message.content,
            metadata_json=message.metadata_json or {},
            tool_calls=message.tool_calls,
            created_time=datetime.now(),
            updated_time=datetime.now()
        )

        db.add(db_message)
        await db.flush()          # 立即获取自增ID
        await db.refresh(db_message)

        return db_message.id

    @classmethod
    async def batch_save_messages_dao(
        cls,
        db: AsyncSession,
        messages: list[SaveAgentMessageModel]
    ) -> list[int]:
        """批量保存多条消息（推荐在一次对话中批量写入）"""
        db_messages = []
        now = datetime.now()

        for msg in messages:
            db_msg = AgentMessage(
                conversation_id=msg.conversation_id,
                user_id=msg.user_id,
                agent_id=msg.agent_id,
                role=msg.role,
                content=msg.content,
                metadata_json=msg.metadata_json or {},
                tool_calls=msg.tool_calls,
                created_time=now,
                updated_time=now
            )
            db_messages.append(db_msg)

        db.add_all(db_messages)
        await db.flush()

        return [m.id for m in db_messages]

    @classmethod
    async def soft_delete_message(cls, db: AsyncSession, message_id: int):
        """软删除单条消息"""
        await db.execute(
            update(AgentMessage)
            .where(AgentMessage.id == message_id)
            .values(is_deleted=True, deleted_time=datetime.now(), updated_time=datetime.now())
        )

    @classmethod
    async def soft_delete_by_conversation(cls, db: AsyncSession, conversation_id: str):
        """软删除整个会话的所有消息"""
        await db.execute(
            update(AgentMessage)
            .where(AgentMessage.conversation_id == conversation_id)
            .values(is_deleted=True, deleted_time=datetime.now(), updated_time=datetime.now())
        )

    @classmethod
    async def update_message_content(
        cls,
        db: AsyncSession,
        message_id: int,
        new_content: str,
        new_metadata: Optional[dict] = None
    ):
        """更新消息内容（用于流式输出完成后更新最终结果）"""
        update_dict = {
            "content": new_content,
            "updated_time": datetime.now()
        }
        if new_metadata is not None:
            update_dict["metadata_json"] = new_metadata

        await db.execute(
            update(AgentMessage)
            .where(AgentMessage.id == message_id)
            .values(**update_dict)
        )
