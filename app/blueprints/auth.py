from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func
from ..extensions import db
from ..integrations import get_identity_provider
from ..integrations.base import IdentityError, IdentityNotActive, ProgramNotRegistered, status_label, status_tone
from ..models import User, StudyProgram
from ..utils import check_rate_limit, dashboard_endpoint, log_action

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(target):
    """Only allow local absolute paths; reject external and protocol-relative URLs."""
    if not target or not isinstance(target, str):
        return None
    target = target.strip()
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target


STATUS_CODE_BY_ERROR = {
    "IdentityNotFound": 404,
    "ProviderUnavailable": 503,
    "ProviderMisconfigured": 503,
    "ProgramNotRegistered": 422,
    "IdentityNotActive": 422,
}


def _normalize_identifier(value):
    return "".join((value or "").split())


def _valid_identifier(value):
    return value.isdigit() and 4 <= len(value) <= 20


def _normalize_name(value):
    cleaned = "".join(ch for ch in (value or "").lower() if ch.isalnum() or ch.isspace())
    return " ".join(cleaned.split())


def _match_program(identity):
    """Cocokkan hasil provider ke study_programs: kode dulu, lalu nama ternormalisasi."""
    if identity.program_code:
        program = StudyProgram.query.filter(
            func.lower(StudyProgram.code) == identity.program_code.strip().lower()
        ).first()
        if program:
            return program
    if identity.program_name:
        target = _normalize_name(identity.program_name)
        for program in StudyProgram.query.filter_by(is_active=True).all():
            if _normalize_name(program.name) == target:
                return program
    return None


def _eligibility(identity):
    """Kembalikan (program, alasan_terblokir). Salah satu bernilai None."""
    if not identity.is_active:
        return None, IdentityNotActive(identity.academic_status).user_message
    program = _match_program(identity)
    if program is None:
        detail = f"{identity.program_name} ({identity.program_code})"
        return None, ProgramNotRegistered(detail).user_message
    return program, None


def _status_code_for(error):
    return STATUS_CODE_BY_ERROR.get(type(error).__name__, 400)


def _resolve_identity(jenis, identifier):
    provider = get_identity_provider()
    return provider.resolve_lecturer(identifier) if jenis == "dosen" else provider.resolve_student(identifier)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = _safe_next_url(request.args.get("next") or request.form.get("next"))
    if current_user.is_authenticated:
        return redirect(next_url or url_for(dashboard_endpoint(current_user.role)))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter(func.lower(User.email) == email).first()
        if not user or not user.check_password(password):
            flash("Email atau password tidak sesuai.", "danger")
        elif not user.active:
            flash("Akun dinonaktifkan. Hubungi administrator.", "warning")
        else:
            login_user(user, remember=bool(request.form.get("remember")))
            log_action("LOGIN", f"Login berhasil untuk role {user.role}")
            db.session.commit()
            return redirect(next_url or url_for(dashboard_endpoint(user.role)))
    return render_template("auth/login.html", page_title="Masuk", next_url=next_url or "")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_endpoint(current_user.role)))
    programs = StudyProgram.query.filter_by(is_active=True).order_by(StudyProgram.name).all()
    if request.method == "POST":
        npm = (request.form.get("npm") or "").strip()
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        program_id = request.form.get("program_id", type=int)
        cohort = (request.form.get("cohort") or "").strip() or None
        program = db.session.get(StudyProgram, program_id) if program_id else None
        if not all([npm, full_name, email, password, program]):
            flash("Semua data wajib diisi dan program studi harus valid.", "danger")
        elif len(password) < 8:
            flash("Password minimal 8 karakter.", "danger")
        elif User.query.filter_by(npm=npm).first():
            flash("NPM sudah terdaftar.", "danger")
        elif User.query.filter(func.lower(User.email) == email).first():
            flash("Email sudah terdaftar.", "danger")
        else:
            user = User(full_name=full_name, email=email, npm=npm, role="student",
                        program_id=program.id, cohort=cohort, active=True)
            user.set_password(password)
            db.session.add(user)
            log_action("STUDENT_REGISTER", f"Mahasiswa {npm} mendaftarkan akun")
            db.session.commit()
            flash("Registrasi berhasil. Silakan login dan daftarkan wajah melalui dashboard.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", page_title="Daftar Akun", programs=programs)


@auth_bp.route("/register/check", methods=["POST"])
def register_check():
    jenis = "dosen" if (request.form.get("jenis") or "").strip().lower() == "dosen" else "mahasiswa"
    field = "nik" if jenis == "dosen" else "npm"
    label = "NIK" if jenis == "dosen" else "NPM"
    identifier = _normalize_identifier(request.form.get(field))

    limit = current_app.config.get("IDENTITY_CHECK_RATE_LIMIT", 10)
    rate_key = request.remote_addr or "unknown"
    if not check_rate_limit(rate_key, limit):
        return (
            render_template("auth/_identity_error.html",
                            message="Terlalu banyak pemeriksaan. Tunggu sebentar."),
            429,
        )

    if not _valid_identifier(identifier):
        return (
            render_template("auth/_identity_error.html",
                            message=f"{label} tidak valid. Gunakan 4 sampai 20 angka."),
            400,
        )

    try:
        identity = _resolve_identity(jenis, identifier)
    except IdentityError as exc:
        current_app.logger.warning("Pemeriksaan identitas gagal: %s", exc.detail or exc)
        return render_template("auth/_identity_error.html", message=exc.user_message), _status_code_for(exc)

    program, blocked_reason = _eligibility(identity)
    lookup_field = "employee_id" if jenis == "dosen" else "npm"
    existing = User.query.filter_by(**{lookup_field: identifier}).first()

    return render_template(
        "auth/_identity_card.html",
        identity=identity,
        status_label=status_label(identity.academic_status),
        status_tone=status_tone(identity.academic_status),
        blocked_reason=blocked_reason,
        already_registered=existing is not None,
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        log_action("LOGOUT", "Pengguna logout")
        db.session.commit()
    logout_user()
    flash("Anda telah keluar dari sistem.", "info")
    return redirect(url_for("auth.login"))
