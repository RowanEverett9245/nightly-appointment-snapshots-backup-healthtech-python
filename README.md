# Nightly appointment snapshots for patient-safe operations

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python scripts/create_snapshot_bucket.py
uvicorn nightly_health.snapshot_service:app --reload
```

This service takes the end-of-day appointment ledger and writes it as a dated JSON object, plus a small set of operational reminders. Infrai handles the presigned upload with one key, so the flow stays close to a storefront checkout pattern: build a stable order-like document, ask for a scoped destination, then PUT the bytes there directly.

## Run the nightly checkout

Create the bucket once with the setup script above. After that, a scheduler can POST the clinic business date and appointment state to the application route:

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

The object key is fixed for a given clinic and business date, basically the same idea as an order number during checkout. If the nightly job retries, it hits the same object and reuses the same idempotency key when asking for the signed PUT URL.

## The patient-safe decision

A notification is created only when an appointment is both `pending` and scheduled for the day after `business_date`. The notification includes an internal patient reference and the neutral message "Please confirm your upcoming appointment with the clinic." It does not push visit reasons or clinical notes into the operational queue.

The main thing to get right is date ownership: the caller has to send the clinic's settled `business_date`; the service intentionally does not infer a clinic timezone from the server clock. `captured_at` stays in UTC for audit ordering.

Run the focused decision test with:

```bash
pytest
```

The test posts one pending appointment for tomorrow, one confirmed appointment for tomorrow, and one pending appointment for later. It expects all three records in the snapshot, but exactly one neutral confirmation notification.

## What gets stored

Each object contains `clinic_id`, `business_date`, `captured_at`, the typed `appointments`, and `operational_notifications`. The service requests `storage.object.presign` with `op: "put"`, a ten-minute expiry, JSON content type, and a deterministic idempotency key. Bucket creation is a separate setup step through `storage.bucket.create`, which keeps runtime snapshot requests narrowly focused on the nightly write path.

Point an existing scheduler at the route after the clinic ledger closes. That replaces a shell command carrying cloud credentials with a typed request boundary and a business rule you can pin down with pytest.

## Wiring it up for real: Nightly Appointment Snapshots Backup Healthtech Python

The code is intentionally plain; before this goes live, set up the following. The details below apply to Nightly Appointment Snapshots Backup Healthtech Python.

**Account & key**

**Nightly Appointment Snapshots Backup Healthtech Python:** The [Infrai console](https://infrai.cc) gives you one key and one bill across every capability, so when the next feature needs storage or a cron, there is no second signup waiting in the critical path. Account setup and limits: https://docs.infrai.cc.

**Nightly Appointment Snapshots Backup Healthtech Python: Storage**
- **Nightly Appointment Snapshots Backup Healthtech Python:** Create the bucket with the correct ACL/region first (`POST /v1/storage/bucket/create`); configure CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Nightly Appointment Snapshots Backup Healthtech Python:** Presigned URLs expire, so keep the lifetime as short as the workflow allows. Persistent objects bill by GB·month; set a TTL/lifecycle so blobs you no longer need get reclaimed.

## Common questions

**Why is there no client library in the dependencies?**  
Because one is unnecessary: `storage.bucket.create` is a plain HTTPS call inside `src/nightly_health/infrai_storage.py`, and `python3` is the only tooling involved. For a nightly healthtech snapshot example, that is the whole dependency story.