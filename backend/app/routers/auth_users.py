from fastapi import APIRouter, Depends

from ..auth import CurrentUser, Identity, get_current_user, get_db, get_identity
from ..config import get_backend_config
from ..db import Database, many, new_id, one
from ..errors import AppError, conflict
from ..schemas import ProfileIn

router = APIRouter(tags=["auth"])


def _me(u: CurrentUser) -> dict:
    role_map = {
        "STUDENT": "student",
        "PROFESSOR": "teacher",
    }

    role = role_map.get(u.role)

    if role is None:
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported user role: {u.role}",
        )

    return {
        "id": u.user_id,
        "name": u.name,
        "email": u.email,
        "role": role,
        "university_id": u.university_id,
        "first_name": u.first_name,
        "last_name": u.last_name,
    }

@router.get("/universities")
def universities(db: Database = Depends(get_db)):
    """For the signup form, which runs BEFORE a session exists. Public by necessity; it exposes only ids and names."""
    with db.tx() as c:
        return {"universities": [{"id": r["university_id"], "name": r["name"]} for r in many(c, "SELECT university_id, name FROM universities ORDER BY name")]}


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return _me(user)


@router.post("/auth/profile", status_code=201)
def create_profile(body: ProfileIn, identity: Identity = Depends(get_identity), db: Database = Depends(get_db)):
    """Create the application profile for the signed-in Supabase user (once). The role is NOT free: instructors must present
    the server-side signup code; students are limited to what enrolment gives them."""
    cfg = get_backend_config()
    if body.role == "PROFESSOR" and cfg.teacher_signup_code and body.teacher_code != cfg.teacher_signup_code:
        raise AppError(403, "That instructor signup code is not valid.", code="bad_teacher_code")
    if body.role == "PROFESSOR" and not cfg.teacher_signup_code and cfg.is_production:
        raise AppError(403, "Instructor signup is disabled.", code="teacher_signup_disabled")
    with db.tx() as c:
        if one(c, "SELECT 1 AS x FROM users WHERE auth_user_id = %s", (identity.auth_user_id,)):
            raise conflict("A profile already exists for this account.", "profile_exists")
        if not one(c, "SELECT 1 AS x FROM universities WHERE university_id = %s", (body.university_id,)):
            raise AppError(422, "Unknown university.")
        user_id = new_id("usr")
        c.execute("INSERT INTO users (user_id, auth_user_id, university_id, email, first_name, last_name, role) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                  (user_id, identity.auth_user_id, body.university_id, identity.email, body.first_name, body.last_name, body.role))
        table, col = ("professors", "professor_id") if body.role == "PROFESSOR" else ("students", "student_id")
        c.execute(f"INSERT INTO {table} ({col}, university_id) VALUES (%s,%s)", (user_id, body.university_id))
        row = one(c, "SELECT user_id, auth_user_id::text AS auth_user_id, university_id, role, email, first_name, last_name FROM users WHERE user_id=%s", (user_id,))
    return _me(CurrentUser(**row))
