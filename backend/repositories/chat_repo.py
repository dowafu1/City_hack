from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import ChatHistory

async def add_chat_message(session: AsyncSession, chat_id: int, role: str, content: str):
    session.add(ChatHistory(chat_id=chat_id, role=role, content=content))
    await session.commit()

async def get_chat_history(session: AsyncSession, chat_id: int):
    result = await session.execute(
        ChatHistory.__table__.select().where(ChatHistory.chat_id == chat_id).order_by(ChatHistory.timestamp)
    )
    return [{"role": r.role, "content": r.content} for r in result.scalars()]
