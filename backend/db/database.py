from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from config import settings

engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300, # Recycle connections every 5 minutes
    connect_args={
        "command_timeout": 60,
        "server_settings": {
            "tcp_user_timeout": "60000" # 60 seconds
        }
    }
)

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all) # careful!
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
