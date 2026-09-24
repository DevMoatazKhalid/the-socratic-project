"""
Instructor analytics. Every number is derived from stored rows and says what it is:

  task_submission      % of the course's PUBLISHED assignments the student has submitted
  socratic_ai_usage    % of published assignments where the student had at least one Coach interaction
  observed_signal_rate % of published assignments with at least one OBSERVED structural review indicator.
                       The AI reports observations only ("pasted a long polished answer"); it never asserts that a student
                       used an external tool, so this is a prompt to look, not a finding.
  mastery              mean score over the student's completed verification results in this course
                       (Strong >= 0.75, Moderate >= 0.5, else Weak); None = not enough evidence yet.
  verification_rate    % of submitted assignments whose verification finished with PASS or PARTIAL
  average_grade        None unless instructor-entered submission scores exist (there is no grading UI yet)
"""
from __future__ import annotations

from typing import Any, Optional

from .auth import CurrentUser
from .db import many, one
from .records import mastery_label
from .views import iso


def _pct(n: int, d: int) -> int:
    return round(100 * n / d) if d else 0


def _name(r) -> str:
    return (" ".join(p for p in (r.get("first_name"), r.get("last_name")) if p)) or (r.get("email") or "").split("@")[0]


def course_students(c, course_id: str, university_id: str) -> list[dict]:
    """Per-student rows for a course (active enrolments only)."""
    total = one(c, "SELECT count(*)::int AS n FROM assignments WHERE course_id=%s AND status='PUBLISHED'", (course_id,))["n"]
    rows = many(c, """
        WITH roster AS (
          SELECT DISTINCT u.user_id, u.first_name, u.last_name, u.email FROM enrollments e JOIN users u ON u.user_id = e.student_id
           WHERE e.course_id = %(c)s AND e.status = 'active' AND e.university_id = %(u)s),
        pub AS (SELECT assignment_id FROM assignments WHERE course_id = %(c)s AND status = 'PUBLISHED')
        SELECT r.*,
          (SELECT count(DISTINCT t.assignment_id) FROM attempts t WHERE t.student_id = r.user_id AND t.status = 'SUBMITTED' AND t.assignment_id IN (SELECT assignment_id FROM pub))::int AS submitted,
          (SELECT count(DISTINCT i.assignment_id) FROM ai_interactions i WHERE i.student_id = r.user_id AND i.assignment_id IN (SELECT assignment_id FROM pub))::int AS coached,
          (SELECT count(DISTINCT s.assignment_id) FROM risk_signals s WHERE s.student_id = r.user_id AND s.assignment_id IN (SELECT assignment_id FROM pub))::int AS signalled,
          (SELECT count(*) FROM risk_signals s WHERE s.student_id = r.user_id AND s.assignment_id IN (SELECT assignment_id FROM pub))::int AS signal_count,
          (SELECT avg(res.score)::float FROM verification_results res JOIN verification_questions q ON q.question_id = res.question_id
             JOIN verification_runs v ON v.verification_id = q.verification_id
            WHERE v.student_id = r.user_id AND v.assignment_id IN (SELECT assignment_id FROM pub) AND res.outcome <> 'INSUFFICIENT_EVIDENCE') AS mastery_score,
          (SELECT count(*) FROM verification_runs v WHERE v.student_id = r.user_id AND v.status = 'COMPLETED' AND v.overall_outcome IN ('PASS','PARTIAL') AND v.assignment_id IN (SELECT assignment_id FROM pub))::int AS verified_ok
        FROM roster r ORDER BY r.last_name NULLS LAST, r.first_name NULLS LAST, r.email""", {"c": course_id, "u": university_id})
    return [{"id": r["user_id"], "name": _name(r), "email": r["email"], "task_submission": _pct(r["submitted"], total),
             "socratic_ai_usage": _pct(r["coached"], total), "observed_signal_rate": _pct(r["signalled"], total),
             "observed_signal_count": r["signal_count"], "mastery": mastery_label(r["mastery_score"]), "_submitted": r["submitted"], "_verified_ok": r["verified_ok"]}
            for r in rows]


def course_dashboard(c, user: CurrentUser, course_id: str) -> dict[str, Any]:
    students = course_students(c, course_id, user.university_id)
    n = len(students)
    submitted = sum(s["_submitted"] for s in students)
    verified = sum(s["_verified_ok"] for s in students)
    grade = one(c, """SELECT avg(sub.score)::float AS g FROM submissions sub JOIN assignments a ON a.assignment_id = sub.assignment_id
                       WHERE a.course_id = %s AND sub.score IS NOT NULL""", (course_id,))["g"]
    metrics = {"assignment_completion": round(sum(s["task_submission"] for s in students) / n) if n else 0,
               "average_grade": None if grade is None else round(grade),
               "socratic_ai_usage": round(sum(s["socratic_ai_usage"] for s in students) / n) if n else 0,
               "observed_signal_rate": round(sum(s["observed_signal_rate"] for s in students) / n) if n else 0,
               "verification_rate": _pct(verified, submitted)}
    return {"metrics": metrics, "students": [{k: v for k, v in s.items() if not k.startswith("_")} for s in students],
            "attention": attention_items(c, course_id, user.university_id), "activity": activity_feed(c, course_id=course_id, university_id=user.university_id, limit=12)}


def attention_items(c, course_id: str, university_id: str) -> list[dict]:
    items: list[dict] = []
    for r in many(c, """
        SELECT v.verification_id, v.student_id, v.assignment_id, v.overall_outcome, a.title, u.first_name, u.last_name, u.email
          FROM verification_runs v JOIN assignments a ON a.assignment_id = v.assignment_id JOIN users u ON u.user_id = v.student_id
         WHERE a.course_id = %s AND v.university_id = %s AND v.status = 'COMPLETED' AND v.overall_outcome IN ('NEEDS_RETRY','PARTIAL')
         ORDER BY v.completed_at DESC LIMIT 4""", (course_id, university_id)):
        items.append({"id": f"rev_{r['verification_id']}", "kind": "review", "tone": "warning", "title": f"Review {_name(r)}'s verification",
                      "description": f"{r['title']}: verification finished as {r['overall_outcome'].replace('_', ' ').lower()}.",
                      "target": {"type": "submission", "assignment_id": r["assignment_id"], "student_id": r["student_id"]}})
    for r in many(c, """
        SELECT s.student_id, count(*)::int AS n, max(s.created_at) AS last_at, u.first_name, u.last_name, u.email
          FROM risk_signals s JOIN assignments a ON a.assignment_id = s.assignment_id JOIN users u ON u.user_id = s.student_id
         WHERE a.course_id = %s AND s.university_id = %s AND s.created_at > now() - interval '14 days'
         GROUP BY s.student_id, u.first_name, u.last_name, u.email ORDER BY n DESC LIMIT 3""", (course_id, university_id)):
        items.append({"id": f"sig_{r['student_id']}", "kind": "signal", "tone": "neutral", "title": f"{r['n']} review indicator(s) for {_name(r)}",
                      "description": "Observed patterns worth a look. These are observations, not a determination of intent.",
                      "target": {"type": "student", "student_id": r["student_id"]}})
    for r in many(c, """
        SELECT a.assignment_id, a.title, a.due_at,
               (SELECT count(*) FROM enrollments e WHERE e.classroom_id = a.classroom_id AND e.status = 'active')::int AS total,
               (SELECT count(DISTINCT t.student_id) FROM attempts t WHERE t.assignment_id = a.assignment_id AND t.status = 'SUBMITTED')::int AS done
          FROM assignments a WHERE a.course_id = %s AND a.status = 'PUBLISHED' AND a.due_at BETWEEN now() AND now() + interval '3 days' ORDER BY a.due_at LIMIT 3""", (course_id,)):
        if r["done"] < r["total"]:
            items.append({"id": f"due_{r['assignment_id']}", "kind": "deadline", "tone": "danger", "title": f"{r['title']} is due soon",
                          "description": f"{r['done']} of {r['total']} students have submitted.", "target": {"type": "assignment", "assignment_id": r["assignment_id"]}})
    return items


def activity_feed(c, *, university_id: str, course_id: Optional[str] = None, student_id: Optional[str] = None, teacher: Optional[CurrentUser] = None, limit: int = 20) -> list[dict]:
    """Learning-evidence feed built from real events (submissions, revisions, completed verifications, coach conversations)."""
    where, params = ["a.university_id = %(u)s"], {"u": university_id, "lim": limit}
    if course_id:
        where.append("a.course_id = %(c)s"); params["c"] = course_id
    if student_id:
        where.append("x.student_id = %(s)s"); params["s"] = student_id
    if teacher:
        where.append("(co.instructor_id = %(t)s OR EXISTS (SELECT 1 FROM classrooms k WHERE k.course_id = co.course_id AND k.professor_id = %(t)s))"); params["t"] = teacher.user_id
    sql = f"""
      SELECT * FROM (
        SELECT t.attempt_id::text AS id, t.ended_at AS at, 'submission' AS kind, t.student_id, t.assignment_id, format('Submitted %%s', 'work') AS detail
          FROM attempts t WHERE t.status = 'SUBMITTED' AND t.ended_at IS NOT NULL
        UNION ALL
        SELECT t.attempt_id, t.started_at, 'revision', t.student_id, t.assignment_id, format('Started revision (attempt %%s)', t.attempt_number)
          FROM attempts t WHERE t.attempt_number > 1
        UNION ALL
        SELECT v.verification_id, v.completed_at, 'verification', v.student_id, v.assignment_id, format('Completed learning verification (%%s)', lower(replace(v.overall_outcome, '_', ' ')))
          FROM verification_runs v WHERE v.status = 'COMPLETED' AND v.completed_at IS NOT NULL
        UNION ALL
        SELECT s.session_id, s.started_at, 'coach_session', s.student_id, s.assignment_id, format('Coach conversation (%%s turns)', s.turn_count)
          FROM ai_sessions s WHERE s.turn_count > 0
      ) x JOIN assignments a ON a.assignment_id = x.assignment_id JOIN courses co ON co.course_id = a.course_id
      WHERE {' AND '.join(where)} ORDER BY x.at DESC LIMIT %(lim)s"""
    return [{"id": f"{r['kind']}_{r['id']}", "date": iso(r["at"]), "course_id": r["course_id"], "assignment_id": r["assignment_id"], "assignment_title": r["title"],
             "kind": r["kind"], "detail": r["detail"], "student_id": r["student_id"]} for r in _feed_rows(c, sql, params)]


def _feed_rows(c, sql, params):
    # x.* has no course/title; join them here so the SELECT list stays simple above
    wrapped = sql.replace("SELECT * FROM (", "SELECT x.id, x.at, x.kind, x.student_id, x.assignment_id, x.detail, a.course_id, a.title FROM (", 1)
    return many(c, wrapped, params)


def student_detail(c, user: CurrentUser, student_id: str) -> dict[str, Any]:
    """One student across the courses this instructor teaches."""
    st = one(c, "SELECT user_id, email, first_name, last_name FROM users WHERE user_id=%s AND university_id=%s", (student_id, user.university_id))
    courses = many(c, """SELECT DISTINCT co.course_id FROM enrollments e JOIN courses co ON co.course_id = e.course_id
                          WHERE e.student_id = %s AND e.status = 'active' AND (co.instructor_id = %s OR EXISTS
                                (SELECT 1 FROM classrooms k WHERE k.course_id = co.course_id AND k.professor_id = %s))""", (student_id, user.user_id, user.user_id))
    ids = [r["course_id"] for r in courses]
    rows = [next((s for s in course_students(c, cid, user.university_id) if s["id"] == student_id), None) for cid in ids]
    rows = [r for r in rows if r]
    avg = lambda k: round(sum(r[k] for r in rows) / len(rows)) if rows else 0  # noqa: E731
    scores = [r for r in many(c, """SELECT avg(res.score)::float AS m FROM verification_results res JOIN verification_questions q ON q.question_id = res.question_id
                                    JOIN verification_runs v ON v.verification_id = q.verification_id JOIN assignments a ON a.assignment_id = v.assignment_id
                                   WHERE v.student_id = %s AND a.course_id = ANY(%s) AND res.outcome <> 'INSUFFICIENT_EVIDENCE'""", (student_id, ids))] if ids else []
    attempts = one(c, "SELECT count(*)::int AS n, count(*) FILTER (WHERE attempt_number > 1)::int AS rev FROM attempts t JOIN assignments a ON a.assignment_id=t.assignment_id WHERE t.student_id=%s AND a.course_id = ANY(%s)", (student_id, ids)) if ids else {"n": 0, "rev": 0}
    struggling = [r["name"] for r in many(c, """SELECT k.name FROM student_concept_state s JOIN concepts k ON k.concept_id = s.concept_id
                                                WHERE s.student_id = %s AND s.university_id = %s AND s.mastery_estimate < 0.5 ORDER BY s.mastery_estimate LIMIT 5""", (student_id, user.university_id))]
    sigs = []
    for r in many(c, """SELECT s.signal, s.observation, s.created_at FROM risk_signals s JOIN assignments a ON a.assignment_id = s.assignment_id
                         WHERE s.student_id = %s AND a.course_id = ANY(%s) ORDER BY s.created_at DESC LIMIT 5""", (student_id, ids or [""])):
        sigs.append({"label": r["signal"].replace("_", " ").capitalize(), "detail": r["observation"] or "Observed by the AI Coach during a conversation.", "tone": "watch"})
    for r in many(c, """SELECT e.evidence_type, e.observation FROM evidence_candidates e JOIN assignments a ON a.assignment_id = e.assignment_id
                         WHERE e.student_id = %s AND a.course_id = ANY(%s) AND e.strength = 'STRONG' ORDER BY e.created_at DESC LIMIT 3""", (student_id, ids or [""])):
        sigs.append({"label": r["evidence_type"].replace("_", " ").capitalize(), "detail": r["observation"], "tone": "positive"})
    return {"id": student_id, "name": _name(st), "email": st["email"], "course_ids": ids,
            "mastery": mastery_label(scores[0]["m"]) if scores else None, "task_submission": avg("task_submission"), "socratic_ai_usage": avg("socratic_ai_usage"),
            "observed_signal_rate": avg("observed_signal_rate"), "attempts": attempts["n"], "revisions": attempts["rev"], "struggling_topics": struggling,
            "signals": sigs, "activity": activity_feed(c, university_id=user.university_id, student_id=student_id, teacher=user, limit=20)}
