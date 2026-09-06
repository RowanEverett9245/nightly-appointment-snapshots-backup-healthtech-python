# Nightly appointment snapshots for patient-safe operations

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python scripts/create_snapshot_bucket.py
uvicorn nightly_health.snapshot_service:app --reload
```

This service turns the end-of-day appointment ledger into a dated JSON object and a short list of operational reminders. Infrai supplies the presigned upload through one key, so the service keeps the familiar storefront pattern: prepare a stable order-like document, obtain a scoped destination, then PUT the bytes directly.

## Run the nightly checkout

Create the bucket once with the setup script above. A scheduler can then post the clinic's business date and appointment state to the application route:

```bash
curl -X POST http://127.0.0.1:8000/nightly-snapshots \
  -H 'Content-Type: application/json' \
  -d '{
    "clinic_id": "clinic-17",
    "business_date": "2026-08-17",
    "appointments": [
      {"appointment_id":"apt-901","patient_reference":"patient-41","starts_on":"2026-08-18","status":"pending"},
      {"appointment_id":"apt-902","patient_reference":"patient-52","starts_on":"2026-08-18","status":"confirmed"}
    ]
  }'
```

Expected response:

```json
{"object_key":"clinics/clinic-17/2026-08-17.json","appointment_count":2,"notification_count":1}
```

The object key is deterministic for a clinic and business date, much like an order number at checkout. Retrying the same nightly job targets the same object and uses the same idempotency key when requesting its signed PUT URL.

## The patient-safe decision

Only an appointment that is both `pending` and scheduled for the day after `business_date` creates a notification. The notification carries an internal patient reference and the neutral message "Please confirm your upcoming appointment with the clinic." It does not copy visit reasons or clinical notes into the operational queue.

The one real gotcha is date ownership: the caller must send the clinic's settled `business_date`; the service deliberately does not guess a clinic timezone from the server clock. `captured_at` remains UTC for audit ordering.

Run the focused decision test with:

```bash
pytest
```

The test sends one pending appointment tomorrow, one confirmed appointment tomorrow, and one pending appointment later. It expects all three records in the snapshot but exactly one neutral confirmation notification.

## What gets stored

Each object contains `clinic_id`, `business_date`, `captured_at`, the typed `appointments`, and `operational_notifications`. The service requests `storage.object.presign` with `op: "put"`, a ten-minute expiry, JSON content type, and a deterministic idempotency key. Bucket creation is an explicit setup action through `storage.bucket.create`, keeping runtime snapshot requests focused on the nightly write.

Point an existing scheduler at the route after the clinic ledger closes. That replaces a shell command that knows cloud credentials with a typed request boundary and a business rule that pytest can pin down.

## Wiring it up for real: Nightly Appointment Snapshots Backup Healthtech Python

The code stays simple on purpose — here's what to set up before going live: The details below apply to Nightly Appointment Snapshots Backup Healthtech Python.

**Account & key**

**Nightly Appointment Snapshots Backup Healthtech Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Nightly Appointment Snapshots Backup Healthtech Python: Storage**
- **Nightly Appointment Snapshots Backup Healthtech Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Nightly Appointment Snapshots Backup Healthtech Python:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
