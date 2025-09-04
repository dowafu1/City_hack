from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Sub

async def get_due_subscribers(session: AsyncSession):
    now = datetime.now().isoformat()
    result = await session.execute(Sub.__table__.select().where(Sub.next_at <= now))
    return [s.user_id for s in result.scalars()]

async def reset_subscriptions(session: AsyncSession, user_ids: list[int]):
    if not user_ids:
        return
    next_at = (datetime.now() + timedelta(days=1)).isoformat()
    await session.execute(
        Sub.__table__.update().where(Sub.user_id.in_(user_ids)).values(next_at=next_at)
    )
    await session.commit()

async def toggle_subscription(session: AsyncSession, user_id: int):
    sub = await session.get(Sub, user_id)
    if sub:
        await session.delete(sub)
        await session.commit()
        return False
    else:
        next_at = (datetime.now() + timedelta(days=1)).isoformat()
        session.add(Sub(user_id=user_id, next_at=next_at))
        await session.commit()
        return True
