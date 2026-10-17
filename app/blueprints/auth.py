from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func
from ..extensions import db
from ..integrations import get_identity_provider, identity_provider_is_sample
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
    """Cocokkan hasil provider ke study_programs: kode dulu, lalu nama ternormalisasi.

    Catatan: status `is_active` sengaja tidak disaring di sini (baik pencarian
    berdasarkan kode maupun nama). Penonaktifan prodi adalah kurasi katalog
    administratif dan tidak boleh memblokir pendaftaran mahasiswa dengan pesan
    keliru bahwa prodi belum terdaftar.
    """
    if identity.program_code:
        program = StudyProgram.query.filter(
            func.lower(StudyProgram.code) == identity.program_code.strip().lower()
        ).first()
        if program:
            return program
    if identity.program_name:
        target = _normalize_name(identity.program_name)
        # is_active sengaja tidak disaring agar konsisten dengan pencarian kode
        for program in StudyProgram.query.all():
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


@auth_bp.route("/register", methods=["GET"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_endpoint(current_user.role)))
    return _render_register(
        jenis="dosen" if (request.args.get("jenis") or "").strip().lower() == "dosen" else "mahasiswa"
    )


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


def _active_programs():
    return StudyProgram.query.filter_by(is_active=True).order_by(StudyProgram.name).all()


def _register_account(jenis, identifier, email, password, password_confirm):
    """Bangun akun dari hasil provider.

    Mengembalikan (user, failure, identity):
    - berhasil: (user, None, identity)
    - gagal:    (None, (pesan, kode), identity_atau_None)

    Identity tetap dikembalikan meski gagal supaya halaman yang dirender ulang
    masih menampilkan kartu konfirmasi. Tanpa itu, pengguna kehilangan konteks
    identitasnya hanya karena salah mengetik kata sandi.
    """
    field = "employee_id" if jenis == "dosen" else "npm"
    label = "NIK" if jenis == "dosen" else "NPM"

    if not _valid_identifier(identifier):
        return None, (f"{label} tidak valid. Gunakan 4 sampai 20 angka.", 400), None
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        return None, ("Masukkan alamat email yang valid.", 400), None
    if len(password) < 8:
        return None, ("Password minimal 8 karakter.", 400), None
    if password != password_confirm:
        return None, ("Konfirmasi kata sandi tidak cocok.", 400), None
    if User.query.filter(func.lower(User.email) == email).first():
        return None, ("Email sudah terdaftar. Silakan masuk.", 400), None
    if User.query.filter_by(**{field: identifier}).first():
        return None, (f"{label} sudah terdaftar. Silakan masuk.", 400), None

    provider = get_identity_provider()
    try:
        identity = (provider.resolve_lecturer(identifier) if jenis == "dosen"
                    else provider.resolve_student(identifier))
    except IdentityError as exc:
        current_app.logger.warning("Pendaftaran gagal pada pemeriksaan identitas: %s", exc.detail or exc)
        return None, (exc.user_message, _status_code_for(exc)), None

    program, blocked_reason = _eligibility(identity)
    if blocked_reason:
        return None, (blocked_reason, 422), identity

    user = User(
        full_name=identity.name,
        email=email,
        role=identity.role,
        program_id=program.id,
        cohort=identity.cohort,
        active=True,
        identity_source=provider.source_code,
    )
    if jenis == "dosen":
        user.employee_id = identity.identifier
        user.nidn = identity.nidn
    else:
        user.npm = identity.identifier
    user.set_password(password)

    db.session.add(user)
    log_action(
        "LECTURER_REGISTER" if jenis == "dosen" else "STUDENT_REGISTER",
        f"{label} {identity.identifier} mendaftar via {provider.source_code}",
    )
    db.session.commit()
    return user, None, identity


def _render_register(status_code=200, **overrides):
    """Render halaman register dengan konteks lengkap yang dibutuhkan template.

    Dipakai oleh jalur GET maupun jalur gagal POST, sehingga kartu konfirmasi
    tidak hilang saat pengguna salah mengetik kata sandi.
    """
    context = {
        "page_title": "Daftar Akun",
        "programs": _active_programs(),
        "jenis": "mahasiswa",
        "sample_mode": identity_provider_is_sample(current_app.config),
        "identity": None,
        "blocked_reason": None,
        "already_registered": False,
    }
    context.update(overrides)
    identity = context.get("identity")
    if identity is not None:
        context["status_label"] = status_label(identity.academic_status)
        context["status_tone"] = status_tone(identity.academic_status)
    return render_template("auth/register.html", **context), status_code


@auth_bp.route("/register/student", methods=["POST"])
def register_student():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_endpoint(current_user.role)))

    identifier = _normalize_identifier(request.form.get("npm"))
    email = (request.form.get("email") or "").strip().lower()
    user, failure, identity = _register_account(
        "mahasiswa", identifier, email,
        request.form.get("password") or "",
        request.form.get("password_confirm") or "",
    )
    if failure:
        message, code = failure
        flash(message, "danger")
        return _render_register(code, jenis="mahasiswa", identity=identity)

    flash("Registrasi berhasil. Silakan login dan daftarkan wajah melalui dashboard.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register/lecturer", methods=["POST"])
def register_lecturer():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_endpoint(current_user.role)))

    identifier = _normalize_identifier(request.form.get("nik"))
    email = (request.form.get("email") or "").strip().lower()
    user, failure, identity = _register_account(
        "dosen", identifier, email,
        request.form.get("password") or "",
        request.form.get("password_confirm") or "",
    )
    if failure:
        message, code = failure
        flash(message, "danger")
        return _render_register(code, jenis="dosen", identity=identity)

    flash("Registrasi berhasil. Silakan login dan lengkapi kelas yang Anda ampu.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        log_action("LOGOUT", "Pengguna logout")
        db.session.commit()
    logout_user()
    flash("Anda telah keluar dari sistem.", "info")
    return redirect(url_for("auth.login"))
