"""
Backend <-> AI boundary. This is the ONLY module that imports the `ai` package (besides the RAG bridge in app/files).

Design rules
  * The AI package is used AS-IS (LangGraph Coach, RAG retrieval, VerificationService). Nothing in `ai/` is modified.
  * The backend decides what the AI may see: university, classroom and an explicit document WHITELIST are computed from
    live database rows and handed over as trusted context. The whitelist is never empty (an empty list means "no
    restriction" inside the AI's retrieval filter), so a classroom without documents fails closed.
  * The AI's objects are converted to plain dicts here, using the AI's real field names, so routers never depend on
    pydantic models from `ai`.
  * LLM failures become AIUnavailable (503) and are NOT persisted as if they were results.
"""
from __future__ import annotations

import concurrent.futures
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import get_backend_config
from .db import Database, many
from .errors import AIUnavailable

log = logging.getLogger("socratiq.ai")

NO_DOCUMENTS_SENTINEL = "__no_documents_allowed__"   # never matches a real document id; makes the whitelist non-empty


def _ensure_ai_importable() -> None:
    root = str(get_backend_config().project_root)
    if root not in sys.path:
        sys.path.insert(0, root)


_ensure_ai_importable()


@dataclass
class CoachOutcome:
    response: str
    intervention: dict[str, Any]
    diagnosis: Optional[dict[str, Any]]
    referenced_concepts: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    risk_signals: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    event_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Challenge:
    verification_type: str
    concept: str
    question: str
    criteria: list[str]


@dataclass
class Evaluation:
    outcome: str
    score: float
    confidence: float
    feedback: str
    criteria: list[dict[str, Any]]
    evidence: Optional[dict[str, Any]]


class DbHistoryProvider:
    """StudentHistoryTool provider: a few relevant prior evidence rows for THIS student (the id is set by the backend,
    never by the model). Same-university only."""

    def __init__(self, db: Database):
        self.db = db

    def __call__(self, student_id: str, assignment_id: str, concept: Optional[str], limit: int = 3):
        from ai.models.schemas import RetrievedContext
        with self.db.tx() as c:
            rows = many(c, """
                SELECT e.evidence_type, e.strength, e.observation, e.concept, e.assignment_id, e.created_at
                  FROM evidence_candidates e
                 WHERE e.student_id = %s AND (e.assignment_id = %s OR (%s::text IS NOT NULL AND lower(e.concept) = lower(%s::text)))
                 ORDER BY (e.assignment_id = %s) DESC, e.created_at DESC LIMIT %s""",
                        (student_id, assignment_id, concept, concept, assignment_id, limit))
        return [RetrievedContext(source="learning_history",
                                 content=f"{r['evidence_type']} ({r['strength']}): {r['observation']}",
                                 metadata={"concept": r["concept"], "assignment_id": r["assignment_id"], "at": r["created_at"].isoformat()})
                for r in rows]


class AIAdapter:
    def __init__(self, coach: Any, verification_service: Any, timeout_seconds: int = 90, max_workers: int = 8):
        self.coach, self.verification = coach, verification_service
        self.timeout = timeout_seconds
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ai")

    def _call(self, fn, *a, **kw):
        fut = self._pool.submit(fn, *a, **kw)
        try:
            return fut.result(timeout=self.timeout)
        except concurrent.futures.TimeoutError as exc:
            raise AIUnavailable("The AI took too long to respond. Please try again.") from exc
        except AIUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("AI call failed")
            raise AIUnavailable() from exc

    # ------------------------------------------------------------------ Coach
    def coach_turn(self, *, student_id: str, assignment: dict, session_id: str, policy: str, attempt_text: str,
                   message: str, history: list[dict], turn_index: int, allowed_document_ids: list[str],
                   student_name: Optional[str] = None, prior: Optional[dict] = None) -> CoachOutcome:
        from langchain_core.messages import AIMessage, HumanMessage
        from ai.agents.coach.state import TaskContext
        from ai.models.schemas import AssistancePolicy, Diagnosis, Intervention

        task = TaskContext(
            assignment_id=assignment["assignment_id"], course_id=assignment["course_id"], title=assignment["title"],
            instructions=assignment["instructions"], subject_area=assignment.get("subject_area"),
            is_programming=bool(assignment.get("is_programming")),
            university_id=assignment["university_id"], classroom_id=assignment.get("classroom_id"),
            allowed_document_ids=list(allowed_document_ids) or [NO_DOCUMENTS_SENTINEL],
            # Optional display-only application context. Missing fields are harmless and never affect
            # authorization; title/instructions remain the authoritative MVP assignment source.
            university_name=assignment.get("university_name"),
            course_code=assignment.get("course_code"),
            course_title=assignment.get("course_title"),
            classroom_name=assignment.get("classroom_name"),
            # PostgreSQL returns timestamp columns as datetime objects; TaskContext deliberately
            # keeps due_at as a display/prompt string. Serialize at the backend -> AI boundary.
            due_at=(assignment.get("due_at").isoformat() if hasattr(assignment.get("due_at"), "isoformat") else assignment.get("due_at")),
            attachments=assignment.get("attachments") or [],
            materials=assignment.get("materials") or [],
            materials_total=int(assignment.get("materials_total") or 0),
        )
        convo = [HumanMessage(content=m["content"]) if m["sender"] == "STUDENT" else AIMessage(content=m["content"]) for m in history]
        prior_dx = prior_iv = None
        if prior:
            try:
                if prior.get("diagnosis"):
                    prior_dx = Diagnosis(**prior["diagnosis"])
                if prior.get("intervention"):
                    prior_iv = Intervention(**prior["intervention"])
            except Exception:  # noqa: BLE001  (a malformed prior must never break the turn)
                prior_dx = prior_iv = None
        result = self._call(self.coach.invoke, student_id=student_id, assignment_id=assignment["assignment_id"], session_id=session_id,
                            task_context=task, attempt=attempt_text, policy=AssistancePolicy(policy), message=message,
                            student_name=student_name,
                            conversation=convo, turn_index=turn_index, prior_diagnosis=prior_dx, prior_intervention=prior_iv)
        return self._normalize_coach(result)

    @staticmethod
    def _normalize_coach(r: Any) -> CoachOutcome:
        dx = r.diagnosis_summary
        return CoachOutcome(
            response=r.response,
            intervention={"type": r.intervention.type.value, "assistance_level": r.intervention.assistance_level.value,
                          "rationale": r.intervention.rationale},
            diagnosis=None if dx is None else {"category": dx.category.value, "concept": dx.concept, "explanation": dx.explanation,
                                               "evidence": dx.evidence, "confidence": float(dx.confidence)},
            referenced_concepts=list(r.referenced_concepts), tools_used=list(r.tools_used),
            evidence=[{"evidence_type": e.evidence_type.value, "strength": e.strength.value, "observation": e.observation,
                       "concept": e.concept} for e in r.evidence_candidates],
            risk_signals=[{"signal": s.signal, "observation": s.observation, "metadata": dict(s.metadata)} for s in r.risk_signals],
            sources=[{"document_id": s.document_id, "document_title": s.document_title, "chunk_id": s.chunk_id,
                      "page_number": s.page_number, "section": s.section, "score": s.score} for s in r.sources],
            event_payload=dict(r.learning_event.payload) if r.learning_event else {})

    # ------------------------------------------------------------------ Verification
    def generate_challenge(self, *, assignment: dict, concept: str, verification_type: str, student_work: str) -> Challenge:
        from ai.verification.models import VerificationChallengeRequest, VerificationType
        ch = self._call(self.verification.generate_challenge, VerificationChallengeRequest(
            assignment_id=assignment["assignment_id"], concept=concept, verification_type=VerificationType(verification_type),
            student_work=student_work[:12000], course_context=(assignment.get("instructions") or "")[:4000] or None))
        return Challenge(verification_type=ch.verification_type.value, concept=ch.concept, question=ch.question, criteria=list(ch.criteria))

    def evaluate(self, *, student_id: str, assignment: dict, concept: str, verification_type: str, question: str,
                 criteria: list[str], answer: str, student_work: str) -> Evaluation:
        from ai.verification.models import VerificationRequest, VerificationType
        res = self._call(self.verification.verify, VerificationRequest(
            student_id=student_id, assignment_id=assignment["assignment_id"], concept=concept,
            verification_type=VerificationType(verification_type), challenge_question=question, student_response=answer,
            criteria=criteria, original_attempt=student_work[:12000] or None))
        # VerificationService.verify() swallows LLM/parse failures and returns INSUFFICIENT_EVIDENCE with score=0,
        # confidence=0 and no rubric. That is an outage, not a judgement about the student: never record it.
        if res.outcome.value == "INSUFFICIENT_EVIDENCE" and res.score == 0.0 and res.confidence == 0.0 and not res.criteria_evaluations:
            raise AIUnavailable("We couldn't evaluate your answer just now. Your answer was not recorded. Please try submitting it again.")
        ev = res.evidence_candidate
        return Evaluation(outcome=res.outcome.value, score=float(res.score), confidence=float(res.confidence), feedback=res.feedback,
                          criteria=[{"criterion": c.criterion, "passed": c.passed, "feedback": c.feedback} for c in res.criteria_evaluations],
                          evidence=None if ev is None else {"evidence_type": ev.evidence_type.value, "strength": ev.strength.value,
                                                            "observation": ev.observation, "concept": ev.concept})


def build_ai_adapter(db: Database, rag: Any) -> AIAdapter:
    """Production wiring of the existing AI components."""
    from ai.agents.coach.graph import Coach
    from ai.tools.course_retrieval import CourseRetrievalTool, RAGCourseRetriever
    from ai.tools.student_history import StudentHistoryTool
    from ai.verification.service import VerificationService
    # RAGCourseRetriever.retrieve_scoped() takes the trusted RetrievalScope built by the Coach graph from TaskContext;
    # its constructor values are only used by the unscoped __call__ path (which the graph does not use when
    # university_id is set, and we always set it).
    retriever = RAGCourseRetriever(rag, university_id="__unscoped_disabled__", classroom_id=None)
    coach = Coach(course_tool=CourseRetrievalTool(retriever=retriever), history_tool=StudentHistoryTool(provider=DbHistoryProvider(db)))
    return AIAdapter(coach, VerificationService())
