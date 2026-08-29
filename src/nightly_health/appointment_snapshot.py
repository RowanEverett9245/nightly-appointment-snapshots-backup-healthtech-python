import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal


@dataclass
class Appointment:
    appointment_id: str
    patient_reference: str
    starts_on: date
    status: Literal["pending", "confirmed", "cancelled", "completed"]

    def __post_init__(self) -> None:
        if isinstance(self.starts_on, str):
            self.starts_on = date.fromisoformat(self.starts_on)
        if self.status not in {"pending", "confirmed", "cancelled", "completed"}:
            raise ValueError(f"Unsupported appointment status: {self.status}")


@dataclass
class SnapshotRequest:
    clinic_id: str
    business_date: date
    appointments: list[Appointment] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.business_date, str):
            self.business_date = date.fromisoformat(self.business_date)
        self.appointments = [
            item if isinstance(item, Appointment) else Appointment(**item)
            for item in self.appointments
        ]


@dataclass
class OperationalNotification:
    appointment_id: str
    patient_reference: str
    kind: Literal["confirmation_needed"] = "confirmation_needed"
    message: str = "Please confirm your upcoming appointment with the clinic."


@dataclass
class SnapshotResult:
    object_key: str
    appointment_count: int
    notification_count: int


def notifications_for(request: SnapshotRequest) -> list[OperationalNotification]:
    next_day = request.business_date + timedelta(days=1)
    return [
        OperationalNotification(
            appointment_id=item.appointment_id,
            patient_reference=item.patient_reference,
        )
        for item in request.appointments
        if item.status == "pending" and item.starts_on == next_day
    ]


async def write_nightly_snapshot(
    request: SnapshotRequest, storage: Any, bucket: str
) -> SnapshotResult:
    notifications = notifications_for(request)
    object_key = f"clinics/{request.clinic_id}/{request.business_date.isoformat()}.json"
    document = {
        "clinic_id": request.clinic_id,
        "business_date": request.business_date.isoformat(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "appointments": [
            {**asdict(item), "starts_on": item.starts_on.isoformat()}
            for item in request.appointments
        ],
        "operational_notifications": [asdict(item) for item in notifications],
    }
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    operation_id = hashlib.sha256(f"{bucket}:{object_key}".encode()).hexdigest()
    signed = await storage.presign_snapshot(bucket, object_key, operation_id)
    await storage.upload_signed(signed["url"], payload)
    return SnapshotResult(
        object_key=object_key,
        appointment_count=len(request.appointments),
        notification_count=len(notifications),
    )
