# Deskia API

## Appointment schedule validation

`GET /appointments/validate-date?business_id=<uuid>&service_name=haircut&requested_start_date=2030-01-07T10:00:00-06:00`

Returns JSON `true` when at least one active staff member is assigned to the
requested service and is available at the requested time; otherwise returns `false`.
Service names use a trimmed, case-insensitive substring match scoped to the
business. When multiple services match, the shortest name is selected first.
The entire service duration (staff override when present), buffer before, and buffer
after must fit both business hours and that staff member's hours without overlapping
a staff block or an active appointment for the business. All block types prevent
availability; touching interval boundaries is allowed. Missing hours, staff, or
service assignments mean unavailable.

Date-specific business schedule exceptions replace the weekly business hours,
including closures and special opening hours. Weekly schedules use Monday=0 through
Sunday=6. The requested time must be in the future and the business must be active.

Datetime offsets are converted to the business's configured IANA timezone. Without
an offset, the datetime is interpreted in that timezone; ambiguous or nonexistent
local times during daylight-saving transitions return HTTP 422 and require an
explicit offset. Missing/malformed parameters and blank service names return 422;
unknown businesses or services return 404, and an invalid configured business
timezone returns 500.

This endpoint checks schedules and existing appointment conflicts but does not
reserve a slot. The existing `/appointments/availability` endpoint remains the
conflict-only check with a fixed one-hour duration.

`staff_hours.business_staff_id` references `business_staff.id`, consistent with staff
service assignments and blocks. Existing database constraints/data must use this
relationship too; changing the Python model does not migrate an existing database.

Run the endpoint checks with:

```sh
uv run pytest -q tests/test_appointment_date_validation.py
```
