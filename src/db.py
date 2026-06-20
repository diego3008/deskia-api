from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from src.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

_async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session():
    async with _async_session_factory() as session:
        yield session
