import os

from fastapi import FastAPI, HTTPException

from .appointment_snapshot import SnapshotRequest, SnapshotResult, write_nightly_snapshot
from .infrai_storage import InfraiError, InfraiStorage

app = FastAPI(title="Nightly appointment snapshots")


@app.post("/nightly-snapshots", response_model=SnapshotResult)
async def create_nightly_snapshot(request: SnapshotRequest) -> SnapshotResult:
    storage = InfraiStorage()
    try:
        return await write_nightly_snapshot(
            request=request,
            storage=storage,
            bucket=os.environ.get("SNAPSHOT_BUCKET", "healthtech-nightly-snapshots"),
        )
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": exc.code, "message": str(exc)}) from exc
    finally:
        await storage.close()
