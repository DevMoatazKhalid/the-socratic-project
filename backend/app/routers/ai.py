from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request

from ..access import allowed_document_ids, student_assignment
from ..auth import CurrentUser, get_db, require_student
from ..config import get_backend_config
from ..db import Database, many, new_id, one
from ..errors import conflict
from ..ratelimit import ai_rate_limit
from ..records import insert_event, insert_evidence, insert_risk_signal
from ..schemas import CoachIn

router = APIRouter(tags=["ai"])
OPEN = ("DRAFT", "IN_PROGRESS")
_KIND = {"HINT": "hint", "QUESTION": "question", "EXPLANATION": "explanation"}


@router.post("/ai/coach", dependencies=[Depends(ai_rate_limit)])
def coach(body: CoachIn, request: Request, user: CurrentUser = Depends(require_student), db: Database = Depends(get_db)):
    """One Socratic Coach turn. Identity, university, classroom, policy and the retrieval whitelist are ALL derived server-side;
    the request only carries the assignment id and the student's message."""
    cfg, ai = get_backend_config(), request.app.state.ai

    # ---- 1) read context (short transaction; no connection is held while the LLM runs)
    with db.tx() as c:
        a = student_assignment(c, user, body.assignment_id)
        att = one(c, "SELECT * FROM attempts WHERE student_id=%s AND assignment_id=%s AND status IN ('DRAFT','IN_PROGRESS')", (user.user_id, a["assignment_id"]))
        if att is None:
            raise conflict("Start an attempt before asking the Coach for help.", "no_open_attempt")
        sess = one(c, "SELECT * FROM ai_sessions WHERE attempt_id=%s AND status='ACTIVE'", (att["attempt_id"],))
        if sess is None:
            c.execute("""INSERT INTO ai_sessions (session_id, student_id, assignment_id, attempt_id, policy, university_id)
                         VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                      (new_id("ses"), user.user_id, a["assignment_id"], att["attempt_id"], a["default_policy"], user.university_id))
            sess = one(c, "SELECT * FROM ai_sessions WHERE attempt_id=%s AND status='ACTIVE'", (att["attempt_id"],))
        history = list(reversed(many(c, "SELECT sender, content FROM messages WHERE session_id=%s ORDER BY created_at DESC, message_id DESC LIMIT %s",
                                     (sess["session_id"], cfg.coach_history_window))))
        last = one(c, """SELECT intervention_type, assistance_level, diagnosis, diagnosis_confidence, diagnosis_explanation, diagnosis_evidence, referenced_concepts
                           FROM ai_interactions WHERE session_id=%s ORDER BY created_at DESC LIMIT 1""", (sess["session_id"],))
        allowed = allowed_document_ids(c, a)
        prior = None
        if last and last["diagnosis"]:
            concepts = last["referenced_concepts"] or []
            prior = {"diagnosis": {"category": last["diagnosis"], "concept": concepts[0] if concepts else None, "explanation": last["diagnosis_explanation"] or "",
                                   "evidence": last["diagnosis_evidence"] or "", "confidence": float(last["diagnosis_confidence"] or 0.0)},
                     "intervention": {"type": last["intervention_type"], "assistance_level": last["assistance_level"], "rationale": "previous turn"}}

    # ---- 2) the AI (policy comes from the assignment row, never from the client)
    out = ai.coach_turn(student_id=user.user_id, student_name=user.name, assignment=a, session_id=sess["session_id"], policy=sess["policy"], attempt_text=att.get("draft_text") or "",
                        message=body.message, history=history, turn_index=sess["turn_count"], allowed_document_ids=allowed, prior=prior)

    # ---- 3) persist the whole turn atomically
    interaction_id, coach_msg_id = new_id("int"), new_id("msg")
    with db.tx() as c:
        c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (sess["session_id"],))         # serialise turns of one session
        cur = one(c, "SELECT status FROM attempts WHERE attempt_id=%s FOR UPDATE", (att["attempt_id"],))
        if cur is None or cur["status"] not in OPEN:
            raise conflict("This attempt was submitted while the Coach was replying.", "attempt_closed")
        dx = out.diagnosis or {}
        c.execute("""INSERT INTO ai_interactions (interaction_id, session_id, student_id, assignment_id, intervention_type, assistance_level, diagnosis,
                        diagnosis_confidence, diagnosis_explanation, diagnosis_evidence, response, referenced_concepts, tools_used, university_id)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)""",
                  (interaction_id, sess["session_id"], user.user_id, a["assignment_id"], out.intervention["type"], out.intervention["assistance_level"],
                   dx.get("category"), dx.get("confidence"), dx.get("explanation"), dx.get("evidence"), out.response,
                   json.dumps(out.referenced_concepts), json.dumps(out.tools_used), user.university_id))
        for rank, s in enumerate(out.sources, start=1):     # provenance, only for chunks that really exist inside THIS tenant/course
            if s.get("chunk_id"):
                c.execute("""INSERT INTO ai_interaction_sources (interaction_id, document_id, chunk_id, final_score, retrieval_rank)
                             SELECT %s, ch.document_id, ch.chunk_id, %s, %s FROM document_chunks ch
                              WHERE ch.chunk_id=%s AND ch.university_id=%s AND ch.course_id=%s ON CONFLICT DO NOTHING""",
                          (interaction_id, s.get("score"), rank, s["chunk_id"], user.university_id, a["course_id"]))
        # clock_timestamp(), not now(): now() is frozen for the whole transaction, which would give both messages the same
        # created_at and make their order in the chat history depend on random ids.
        c.execute("INSERT INTO messages (message_id, session_id, sender, content, created_at) VALUES (%s,%s,'STUDENT',%s, clock_timestamp())",
                  (new_id("msg"), sess["session_id"], body.message))
        c.execute("INSERT INTO messages (message_id, session_id, sender, content, interaction_id, created_at) VALUES (%s,%s,'COACH',%s,%s, clock_timestamp())",
                  (coach_msg_id, sess["session_id"], out.response, interaction_id))
        event_id = insert_event(c, student_id=user.user_id, university_id=user.university_id, event_type="AI_INTERACTION", assignment_id=a["assignment_id"],
                                session_id=sess["session_id"], attempt_id=att["attempt_id"], interaction_id=interaction_id,
                                payload={"intervention": out.intervention["type"], "diagnosis": dx.get("category"), "concepts": out.referenced_concepts,
                                         "sources": len(out.sources), "tools_used": out.tools_used})
        for ev in out.evidence:
            insert_evidence(c, student_id=user.user_id, university_id=user.university_id, assignment_id=a["assignment_id"], ev=ev, event_id=event_id)
        for sig in out.risk_signals:
            insert_risk_signal(c, student_id=user.user_id, university_id=user.university_id, assignment_id=a["assignment_id"],
                               session_id=sess["session_id"], event_id=event_id, sig=sig)
        turn = one(c, "UPDATE ai_sessions SET turn_count = turn_count + 1 WHERE session_id=%s RETURNING turn_count", (sess["session_id"],))["turn_count"]

    return {"interaction_id": interaction_id, "turn": turn,
            "message": {"id": coach_msg_id, "role": "coach", "content": out.response, "kind": _KIND.get(out.intervention["type"])},
            "intervention": {"type": out.intervention["type"]},
            "sources": [{"document_title": s.get("document_title"), "page_number": s.get("page_number"), "section": s.get("section")} for s in out.sources]}
