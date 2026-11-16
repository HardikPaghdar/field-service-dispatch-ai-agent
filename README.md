# Field Service Dispatch AI Agent

A practical dispatch-planning API for a small HVAC / field-service operator. It turns incoming service requests into priority assessments, ranks technicians by skill and availability, checks schedule conflicts, and creates a **proposed** dispatch that requires a human manager's approval.

> This is a runnable decision-support demo using synthetic data and deterministic rules. It does not contact customers, book calendars, access live maps, or dispatch technicians automatically.

## Scenario
A service coordinator receives repair calls throughout the day. The system identifies safety-sensitive and SLA-sensitive jobs, matches the required skills to technicians, and proposes a time slot without double-booking anyone.

## Features
- Service request intake with urgency and required-skill assessment
- Technician matching using skills, territory and active workload
- Schedule conflict checks and candidate time-slot suggestions
- Dispatch proposal with customer-message draft
- Explicit manager approval before a proposal becomes approved
- JSON API, sample dataset, automated tests and container setup

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs.

## Example
```bash
curl -X POST http://127.0.0.1:8000/dispatch/proposals \
  -H 'Content-Type: application/json' \
  -d '{"request_id":"SR-1001","preferred_date":"2026-11-17","duration_minutes":90}'
```
Use the returned proposal ID with `POST /dispatch/proposals/{proposal_id}/approve`.

## API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | Health check |
| GET | /technicians | Technician roster |
| GET | /requests | Service requests |
| POST | /requests/assess | Assess priority and skills |
| POST | /dispatch/proposals | Generate ranked dispatch proposal |
| POST | /dispatch/proposals/{id}/approve | Manager approval |

## Project structure
- `app/main.py` — API, matching, scheduling and approval workflow
- `data/` — synthetic requests, technicians and existing appointments
- `tests/` — API and business-rule tests
- `docs/architecture.svg` — architecture overview

## Configuration
Copy `.env.example` to `.env`. The demo currently has no required external credentials. Territory and schedule data are local JSON fixtures.

## Decision logic
Priority is rule-based: safety indicators rank highest, followed by service-level urgency and customer impact. Technician ranking considers required skill coverage, territory match and current workload. Slot suggestions reject overlapping appointments. The score is an explainable heuristic, not a trained model or an SLA guarantee.

## Safety and limitations
- A manager must approve every dispatch proposal.
- Data is synthetic; there is no authentication, persistence layer, calendar sync, routing API or notification provider.
- In-memory proposal state resets when the process restarts.
- Do not use this demo to make emergency or safety-critical decisions.

## Next steps
Production extensions could add PostgreSQL persistence, role-based access, Google Maps travel-time estimates, calendar integrations, SMS/email delivery and an audited approval history.
