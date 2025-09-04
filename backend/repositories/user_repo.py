from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import User


async def get_role(session: AsyncSession, user_id: int):
  user = await session.get(User, user_id)
  return user.role if user else None


async def set_role(session: AsyncSession, user_id: int, role: str):
  user = await session.get(User, user_id)
  if not user:
    user = User(user_id=user_id, role=role)
    session.add(user)
  else:
    user.role = role
  await session.commit()
