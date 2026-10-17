import threading
import time
from functools import wraps
from datetime import datetime
from flask import abort, request
from flask_login import current_user
from .extensions import db
from .models import ActivityLog, Semester


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def log_action(action: str, details: str = ""):
    actor_id = current_user.id if getattr(current_user, "is_authenticated", False) else None
    log = ActivityLog(
        actor_id=actor_id,
        action=action[:100],
        details=(details or "")[:700],
        ip_address=(request.headers.get("X-Forwarded-For", request.remote_addr) or "")[:64],
        created_at=datetime.now(),
    )
    db.session.add(log)


def get_active_semester():
    return Semester.query.filter_by(is_active=True).first()


def dashboard_endpoint(role: str) -> str:
    return {"admin": "admin.dashboard", "lecturer": "lecturer.dashboard", "student": "student.dashboard"}.get(role, "main.index")


def finalize_expired_sessions(now=None):
    """Close expired active sessions and mark approved participants without a record ABSENT.

    Idempotent: repeated calls do not add duplicate attendance rows.
    Called on authenticated requests so expired sessions are finalized even if
    the lecturer does not return to the class detail page immediately.
    """
    from .models import AttendanceSession, CourseEnrollment, Attendance, ActivityLog

    now = now or datetime.now()
    expired = AttendanceSession.query.filter(
        AttendanceSession.status == "ACTIVE",
        AttendanceSession.closes_at <= now,
    ).all()
    if not expired:
        return 0

    finalized = 0
    try:
        for session in expired:
            approved = CourseEnrollment.query.filter_by(
                offering_id=session.offering_id, status="APPROVED"
            ).all()
            existing_ids = {row.student_id for row in Attendance.query.filter_by(session_id=session.id).all()}
            missing = 0
            for enrollment in approved:
                if enrollment.student_id not in existing_ids:
                    db.session.add(Attendance(
                        session_id=session.id,
                        student_id=enrollment.student_id,
                        status="ABSENT",
                        checked_in_at=None,
                        verification_method="SESSION_FINALIZATION",
                    ))
                    missing += 1
            session.status = "CLOSED"
            session.closed_at = now
            db.session.add(ActivityLog(
                actor_id=None,
                action="SESSION_AUTO_FINALIZE",
                details=f"Sesi #{session.session_number} kelas {session.offering.course.code} {session.offering.class_code} otomatis ditutup setelah batas waktu; {missing} mahasiswa difinalisasi ABSENT.",
                created_at=now,
            ))
            finalized += 1
        db.session.commit()
        return finalized
    except Exception:
        db.session.rollback()
        raise


# ponytail: pembatas berbasis memori dalam satu proses; beralih ke Redis bila memakai banyak worker.
_rate_limit_lock = threading.Lock()
_rate_limit_hits = {}


def check_rate_limit(key, limit, window_seconds=60):
    """True bila permintaan masih diizinkan; sekaligus menambah satu hitungan."""
    if limit <= 0:
        return True

    now = time.monotonic()
    cutoff = now - window_seconds
    with _rate_limit_lock:
        hits = [stamp for stamp in _rate_limit_hits.get(key, []) if stamp > cutoff]
        if len(hits) >= limit:
            _rate_limit_hits[key] = hits
            return False
        hits.append(now)
        _rate_limit_hits[key] = hits
        return True


def reset_rate_limit():
    """Kosongkan seluruh hitungan. Dipakai fixture pengujian antar-tes."""
    with _rate_limit_lock:
        _rate_limit_hits.clear()

