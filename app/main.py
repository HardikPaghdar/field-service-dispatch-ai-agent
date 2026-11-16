"""Human-approved field service dispatch planning demo."""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_json(name: str) -> list[dict[str, Any]]:
    with (DATA / name).open(encoding="utf-8") as handle:
        return json.load(handle)


TECHNICIANS = load_json("technicians.json")
REQUESTS = load_json("service_requests.json")
APPOINTMENTS = load_json("appointments.json")
PROPOSALS: dict[str, dict[str, Any]] = {}

app = FastAPI(title="Field Service Dispatch AI Agent", version="0.1.0",
              description="Explainable dispatch recommendations with mandatory human approval.")


class AssessInput(BaseModel):
    request_id: str


class ProposalInput(BaseModel):
    request_id: str
    preferred_date: date
    duration_minutes: int = Field(default=90, ge=15, le=480)


def get_request(request_id: str) -> dict[str, Any]:
    item = next((r for r in REQUESTS if r["id"] == request_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Service request not found")
    return item


def assess(request: dict[str, Any]) -> dict[str, Any]:
    text = " ".join([request.get("description", ""), *request.get("tags", [])]).lower()
    if any(word in text for word in ("gas leak", "smoke", "electrical burning", "carbon monoxide")):
        priority, score, reason = "critical", 100, "Potential safety hazard; escalate to a qualified human immediately."
    elif request.get("sla_hours", 99) <= 4 or request.get("equipment_down"):
        priority, score, reason = "high", 80, "Short SLA or equipment outage."
    elif request.get("sla_hours", 99) <= 24:
        priority, score, reason = "medium", 55, "Service-level target is within 24 hours."
    else:
        priority, score, reason = "normal", 25, "No urgent indicator found."
    skills = set(request.get("required_skills", []))
    if "cooling" in text or "air conditioning" in text:
        skills.add("hvac")
    return {"request_id": request["id"], "priority": priority, "priority_score": score,
            "required_skills": sorted(skills), "reason": reason,
            "human_review_required": True}


def overlaps(start: datetime, end: datetime, appointment: dict[str, Any]) -> bool:
    a_start = datetime.fromisoformat(appointment["start"])
    a_end = datetime.fromisoformat(appointment["end"])
    return start < a_end and end > a_start


def rank_technicians(request: dict[str, Any], day: date, duration: int) -> list[dict[str, Any]]:
    assessment = assess(request)
    required = set(assessment["required_skills"])
    territory = request["territory"]
    ranked = []
    for tech in TECHNICIANS:
        skills = set(tech["skills"])
        missing = sorted(required - skills)
        territory_match = territory in tech["territories"]
        day_start = datetime.combine(day, time(8, 0))
        day_end = datetime.combine(day, time(18, 0))
        busy = [a for a in APPOINTMENTS if a["technician_id"] == tech["id"]
                and datetime.fromisoformat(a["start"]).date() == day]
        occupied = sum(max(0, (datetime.fromisoformat(a["end"]) -
                              datetime.fromisoformat(a["start"])).seconds // 60) for a in busy)
        free_minutes = max(0, 600 - occupied)
        slots = []
        cursor = day_start
        while cursor + timedelta(minutes=duration) <= day_end:
            end = cursor + timedelta(minutes=duration)
            if all(not overlaps(cursor, end, a) for a in busy):
                slots.append({"start": cursor.isoformat(), "end": end.isoformat()})
                break
            cursor += timedelta(minutes=30)
        score = (50 if not missing else max(0, 35 - 12 * len(missing))) + (25 if territory_match else 0)
        score += min(25, free_minutes / 24)
        if not slots:
            score = 0
        ranked.append({"technician_id": tech["id"], "name": tech["name"],
                       "matched_skills": sorted(required & skills), "missing_skills": missing,
                       "territory_match": territory_match, "available_minutes_estimate": free_minutes,
                       "score": round(score, 1), "suggested_slot": slots[0] if slots else None,
                       "eligible": not missing and territory_match and bool(slots)})
    return sorted(ranked, key=lambda x: (x["eligible"], x["score"]), reverse=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": os.getenv("ENVIRONMENT", "development")}


@app.get("/technicians")
def list_technicians() -> list[dict[str, Any]]:
    return TECHNICIANS


@app.get("/requests")
def list_requests() -> list[dict[str, Any]]:
    return REQUESTS


@app.post("/requests/assess")
def assess_request(payload: AssessInput) -> dict[str, Any]:
    return assess(get_request(payload.request_id))


@app.post("/dispatch/proposals")
def create_proposal(payload: ProposalInput) -> dict[str, Any]:
    request = get_request(payload.request_id)
    assessment = assess(request)
    ranked = rank_technicians(request, payload.preferred_date, payload.duration_minutes)
    selected = next((item for item in ranked if item["eligible"]), None)
    proposal = {"id": str(uuid.uuid4()), "request": request, "assessment": assessment,
                "ranked_technicians": ranked, "selected_technician": selected,
                "status": "needs_manager_approval",
                "customer_message_draft": (
                    f"We have a proposed service visit for {payload.preferred_date.isoformat()}. "
                    "Our coordinator will confirm the appointment after review."
                ),
                "approval": None}
    PROPOSALS[proposal["id"]] = proposal
    return proposal


@app.post("/dispatch/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, manager: str = "demo-manager") -> dict[str, Any]:
    proposal = PROPOSALS.get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal["status"] != "needs_manager_approval":
        raise HTTPException(status_code=409, detail="Proposal is not awaiting approval")
    if not proposal["selected_technician"]:
        raise HTTPException(status_code=409, detail="No eligible technician/slot; cannot approve")
    proposal["status"] = "approved"
    proposal["approval"] = {"manager": manager, "approved_at": datetime.utcnow().isoformat() + "Z"}
    return proposal
