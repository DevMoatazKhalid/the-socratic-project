"""Writers for the learning-process record: events, evidence, risk indicators, concept state.
Everything is written inside the caller's transaction, so a record can never exist without the thing that caused it."""
from __future__ import annotations

import json
from typing import Any, Optional

import psycopg

from .db import new_id, one

MASTERY_METHOD = "mean_verification_score_v1"


def insert_event(conn: psycopg.Connection, *, student_id: str, university_id: str, event_type: str, assignment_id: Optional[str] = None,
                 session_id: Optional[str] = None, attempt_id: Optional[str] = None, interaction_id: Optional[str] = None,
                 verification_id: Optional[str] = None, payload: Optional[dict] = None) -> str:
    event_id = new_id("evt")
    conn.execute("""INSERT INTO learning_events (event_id, student_id, assignment_id, session_id, attempt_id, interaction_id, verification_id,
                    event_type, payload, university_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                 (event_id, student_id, assignment_id, session_id, attempt_id, interaction_id, verification_id, event_type,
                  json.dumps(payload or {}, default=str), university_id))
    return event_id


def insert_evidence(conn: psycopg.Connection, *, student_id: str, university_id: str, assignment_id: str, ev: dict[str, Any],
                    event_id: Optional[str] = None) -> str:
    evidence_id = new_id("evd")
    conn.execute("""INSERT INTO evidence_candidates (evidence_id, student_id, assignment_id, concept, evidence_type, strength, observation, university_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                 (evidence_id, student_id, assignment_id, ev.get("concept"), ev["evidence_type"], ev["strength"], ev["observation"][:2000], university_id))
    if event_id:
        conn.execute("INSERT INTO evidence_sources (evidence_id, event_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (evidence_id, event_id))
    return evidence_id


def insert_risk_signal(conn: psycopg.Connection, *, student_id: str, university_id: str, assignment_id: str, session_id: str,
                       event_id: Optional[str], sig: dict[str, Any]) -> None:
    # severity/confidence stay NULL: the AI reports what it OBSERVED and never rates or asserts intent.
    conn.execute("""INSERT INTO risk_signals (risk_signal_id, student_id, assignment_id, session_id, learning_event_id, signal, observation, metadata, university_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                 (new_id("rsk"), student_id, assignment_id, session_id, event_id, sig["signal"][:120], (sig.get("observation") or "")[:2000],
                  json.dumps(sig.get("metadata") or {}, default=str), university_id))


def update_concept_state(conn: psycopg.Connection, *, student_id: str, university_id: str, concept_name: str) -> None:
    """Mastery estimate for one concept = mean score over this student's COMPLETED verification results on it.
    Deliberately simple and transparent (method recorded in state_metadata); only real assessments count, never chat behaviour."""
    name = concept_name.strip()[:200]
    if not name:
        return
    concept = one(conn, """INSERT INTO concepts (university_id, name) VALUES (%s,%s)
                           ON CONFLICT (university_id, normalized_name) DO UPDATE SET name = concepts.name RETURNING concept_id""", (university_id, name))
    stats = one(conn, """
        SELECT avg(r.score)::float AS mean_score, avg(r.confidence)::float AS mean_conf, count(*)::int AS n
          FROM verification_results r
          JOIN verification_questions q ON q.question_id = r.question_id
          JOIN verification_runs v ON v.verification_id = q.verification_id
         WHERE v.student_id = %s AND v.university_id = %s AND lower(btrim(q.concept)) = lower(btrim(%s))
           AND r.outcome <> 'INSUFFICIENT_EVIDENCE'""", (student_id, university_id, name))
    if not stats or not stats["n"]:
        return
    conn.execute("""
        INSERT INTO student_concept_state (student_id, concept_id, mastery_estimate, confidence, evidence_count, last_evaluated_at, state_metadata, university_id)
        VALUES (%s,%s,%s,%s,%s, now(), %s::jsonb, %s)
        ON CONFLICT (student_id, concept_id) DO UPDATE SET mastery_estimate = EXCLUDED.mastery_estimate, confidence = EXCLUDED.confidence,
              evidence_count = EXCLUDED.evidence_count, last_evaluated_at = now(), state_metadata = EXCLUDED.state_metadata""",
                 (student_id, concept["concept_id"], round(stats["mean_score"], 4), round(stats["mean_conf"], 4), stats["n"],
                  json.dumps({"method": MASTERY_METHOD}), university_id))


def mastery_label(mastery: Optional[float], evidence_count: int = 1) -> Optional[str]:
    """None = not enough evidence. Thresholds are documented in docs/API.md."""
    if mastery is None or evidence_count < 1:
        return None
    return "Strong" if mastery >= 0.75 else "Moderate" if mastery >= 0.5 else "Weak"
