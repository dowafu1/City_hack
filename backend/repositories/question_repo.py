from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Question

async def save_question(session: AsyncSession, user_id: int, text: str):
    session.add(Question(user_id=user_id, question=text, timestamp=datetime.now().isoformat()))
    await session.commit()
