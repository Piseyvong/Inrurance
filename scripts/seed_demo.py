"""Seed the coherent local portal demo accounts and product data."""
import asyncio

from app.database import SessionLocal
from app.services.portal_service import seed_demo


async def main() -> None:
    async with SessionLocal() as db:
        print(await seed_demo(db))


if __name__ == "__main__":
    asyncio.run(main())
