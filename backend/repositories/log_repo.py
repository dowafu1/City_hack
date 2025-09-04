from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Log

async def log_action(session: AsyncSession, user_id: int, action: str):
    session.add(Log(user_id=user_id, action=action, timestamp=datetime.now().isoformat()))
    await session.commit()
