import asyncio
from datetime import date

from nightly_health.appointment_snapshot import Appointment, SnapshotRequest, write_nightly_snapshot


class RecordingStorage:
    def __init__(self) -> None:
        self.payload = b""
        self.key = ""

    async def presign_snapshot(self, bucket: str, key: str, idempotency_key: str) -> dict:
        self.key = key
        assert bucket == "nightly"
        assert len(idempotency_key) == 64
        return {"url": "https://uploads.example/snapshot"}

    async def upload_signed(self, url: str, payload: bytes) -> None:
        assert url == "https://uploads.example/snapshot"
        self.payload = payload


def test_snapshot_notifies_only_tomorrows_pending_appointments() -> None:
    request = SnapshotRequest(
        clinic_id="clinic-17",
        business_date=date(2026, 8, 17),
        appointments=[
            Appointment(appointment_id="apt-pending", patient_reference="patient-41", starts_on=date(2026, 8, 18), status="pending"),
            Appointment(appointment_id="apt-confirmed", patient_reference="patient-52", starts_on=date(2026, 8, 18), status="confirmed"),
            Appointment(appointment_id="apt-later", patient_reference="patient-63", starts_on=date(2026, 8, 19), status="pending"),
        ],
    )
    storage = RecordingStorage()

    result = asyncio.run(write_nightly_snapshot(request, storage, "nightly"))

    document = __import__("json").loads(storage.payload)
    assert result.object_key == "clinics/clinic-17/2026-08-17.json"
    assert result.notification_count == 1
    assert document["operational_notifications"] == [
        {
            "appointment_id": "apt-pending",
            "kind": "confirmation_needed",
            "message": "Please confirm your upcoming appointment with the clinic.",
            "patient_reference": "patient-41",
        }
    ]
