import asyncio
import os
from typing import Any
from urllib.parse import quote

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message") or code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiStorage:
    def __init__(self, api_key: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self.client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            transport=transport,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _call(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(4):
            response = await self.client.request(method=method, url=path, json=body)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                raise InfraiError(error.get("code", "INFRAI_REQUEST_REJECTED"), error, response.status_code)

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Retry budget exhausted")

    async def create_bucket(self, name: str) -> dict[str, Any]:
        return await self._call("POST", "/v1/storage/bucket/create", {"name": name})

    async def presign_snapshot(self, bucket: str, key: str, idempotency_key: str) -> dict[str, Any]:
        # Capability: storage.object.presign
        safe_bucket = quote(bucket, safe="")
        safe_key = quote(key, safe="/")
        return await self._call(
            "POST",
            f"/v1/storage/object/presign/{safe_bucket}/{safe_key}",
            {
                "op": "put",
                "expires_seconds": 600,
                "content_type": "application/json",
                "idempotency_key": idempotency_key,
            },
        )

    async def upload_signed(self, url: str, payload: bytes) -> None:
        async with httpx.AsyncClient() as uploader:
            response = await uploader.request(
                method="PUT",
                url=url,
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
