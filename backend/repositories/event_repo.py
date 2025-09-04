from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Event

async def upsert_event(session: AsyncSession, title, date, desc, link):
    session.add(Event(title=title, date=date, description=desc, link=link))
    await session.commit()

async def get_events(session: AsyncSession):
    result = await session.execute(Event.__table__.select())
    return [(e.title, e.date, e.description, e.link) for e in result.scalars()]
