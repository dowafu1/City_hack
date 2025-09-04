from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Contact

async def upsert_contact(session: AsyncSession, category, name, phone, description):
    session.add(Contact(category=category, name=name, phone=phone, description=description))
    await session.commit()

async def get_contacts(session: AsyncSession):
    result = await session.execute(Contact.__table__.select())
    return [(c.category, c.name, c.phone, c.description) for c in result.scalars()]
