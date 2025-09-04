from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from backend.database.models import Tip

async def upsert_tip(session: AsyncSession, text: str):
    session.add(Tip(text=text))
    await session.commit()

async def get_tip(session: AsyncSession):
    result = await session.execute(Tip.__table__.select().order_by(func.random()).limit(1))
    row = result.scalars().first()
    return row.text if row else "Совет дня: подыши глубже, это помогает. 😊"
