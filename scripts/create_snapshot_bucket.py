import asyncio
import os

from nightly_health.infrai_storage import InfraiStorage


async def main() -> None:
    bucket = os.environ.get("SNAPSHOT_BUCKET", "healthtech-nightly-snapshots")
    storage = InfraiStorage()
    try:
        await storage.create_bucket(bucket)
        print(f"Snapshot bucket ready: {bucket}")
    finally:
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
