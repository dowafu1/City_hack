from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import SosInstruction

async def upsert_sos(session: AsyncSession, text: str):
    await session.execute(SosInstruction.__table__.delete())
    session.add(SosInstruction(text=text))
    await session.commit()

async def get_sos(session: AsyncSession):
    result = await session.execute(SosInstruction.__table__.select().limit(1))
    row = result.scalars().first()
    return row.text if row else "🆘 При опасности звоните 112 или 102."
