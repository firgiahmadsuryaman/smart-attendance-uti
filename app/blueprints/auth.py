from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func
from ..extensions import db
from ..models import User, StudyProgram
from ..utils import dashboard_endpoint, log_action

auth_bp = Blueprint("auth", __name__)


def _safe_next_url(target):
    """Only allow local absolute paths; reject external and protocol-relative URLs."""
    if not target or not isinstance(target, str):
        return None
    target = target.strip()
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target


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


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        log_action("LOGOUT", "Pengguna logout")
        db.session.commit()
    logout_user()
    flash("Anda telah keluar dari sistem.", "info")
    return redirect(url_for("auth.login"))
