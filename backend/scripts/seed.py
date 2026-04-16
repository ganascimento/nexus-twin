import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from src.database.seed import seed_default_world  # noqa: E402


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with AsyncSession(engine) as session:
        await seed_default_world(session)
        await session.commit()
    await engine.dispose()
    print("Seed completed — default world populated.")


if __name__ == "__main__":
    asyncio.run(main())
