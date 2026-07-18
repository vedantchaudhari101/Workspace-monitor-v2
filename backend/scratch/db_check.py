import asyncio
from app.database import async_session_factory
from sqlalchemy import select
from app.models.seat import Seat
from app.models.zone import Zone

async def main():
    async with async_session_factory() as session:
        r = await session.execute(select(Seat.zone_id))
        seats = r.scalars().all()
        print(f"Total seats in DB: {len(seats)}")
        
        zones = {}
        for z in seats:
            zones[z] = zones.get(z, 0) + 1
        print(f"Seats per zone: {zones}")

if __name__ == "__main__":
    asyncio.run(main())
