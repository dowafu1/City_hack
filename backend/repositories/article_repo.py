from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Article

async def upsert_article(session: AsyncSession, category, title, content):
    session.add(Article(category=category, title=title, content=content))
    await session.commit()

async def get_articles(session: AsyncSession, category: str):
    result = await session.execute(Article.__table__.select().where(Article.category == category))
    return [(a.title, a.content) for a in result.scalars()]
