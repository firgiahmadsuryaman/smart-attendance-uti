import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, redirect, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from .extensions import db, login_manager, migrate, csrf

DEMO_STUDY_PROGRAMS = [
    ("SING", "Sastra Inggris"),
    ("PMAT", "Pendidikan Matematika"),
    ("PBI", "Pendidikan Bahasa Inggris"),
    ("POR", "Pendidikan Olahraga"),
    ("BI", "Bahasa Inggris"),
    ("D3BI", "D3 Bahasa Inggris"),
    ("SI", "Sistem Informasi"),
    ("IF", "Informatika"),
    ("TI", "Teknologi Informasi"),
    ("TS", "Teknik Sipil"),
    ("TE", "Teknik Elektro"),
    ("TK", "Teknik Komputer"),
    ("IK", "Ilmu Komputer"),
    ("MNJ", "Manajemen"),
    ("AKT", "Akuntansi"),
]


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    default_db = f"sqlite:///{Path(app.instance_path, 'smart_attendance.db').as_posix()}"
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-this-secret"),
        SQLALCHEMY_DATABASE_URI=(os.getenv("DATABASE_URL", "").strip() or default_db),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        WTF_CSRF_TIME_LIMIT=3600,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_HTTPONLY=True,
        DEBUG=os.getenv("FLASK_DEBUG", "0") == "1",
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Silakan login terlebih dahulu."
    login_manager.login_message_category = "warning"

    from . import models  # noqa: F401
    from .blueprints.auth import auth_bp
    from .blueprints.main import main_bp
    from .blueprints.admin import admin_bp
    from .blueprints.lecturer import lecturer_bp
    from .blueprints.student import student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(lecturer_bp)
    app.register_blueprint(student_bp)

    @app.before_request
    def reject_inactive_account_and_finalize_sessions():
        from flask import flash, redirect, request, url_for
        from flask_login import logout_user
        if current_user.is_authenticated and not getattr(current_user, "active", True):
            logout_user()
            flash("Akun Anda telah dinonaktifkan. Hubungi administrator jika ini keliru.", "warning")
            return redirect(url_for("auth.login"))
        if current_user.is_authenticated and request.endpoint != "static":
            # A request-driven fallback finalizes expired sessions without requiring
            # a separate scheduler. The operation is idempotent and safely rollbacked.
            from .utils import finalize_expired_sessions
            try:
                finalize_expired_sessions()
            except Exception:
                app.logger.exception("Gagal memfinalisasi sesi presensi yang kedaluwarsa.")

    @app.errorhandler(500)
    def internal_server_error(error):
        # Keep the detailed exception in the server log; do not expose internals
        # or credentials in the browser response.
        original = getattr(error, "original_exception", None)
        if original is not None:
            app.logger.error(
                "Permintaan gagal dengan HTTP 500.",
                exc_info=(type(original), original, original.__traceback__),
            )
        else:
            app.logger.error("Permintaan gagal dengan HTTP 500: %s", error)
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import render_template
        return render_template("errors/500.html"), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        from flask import flash, redirect, request
        flash("Formulir kedaluwarsa atau token keamanan tidak valid. Muat ulang halaman dan coba lagi.", "warning")
        return redirect(request.referrer or url_for("main.index"))

    @app.errorhandler(403)
    def forbidden(_error):
        from flask import render_template
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        from .models import Notification, CourseEnrollment
        unread = 0
        pending_enrollments = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            if current_user.role == "admin":
                pending_enrollments = CourseEnrollment.query.filter_by(status="PENDING").count()
        return {"current_year": datetime.now().year, "unread_notifications": unread,
                "pending_enrollments": pending_enrollments}

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables for a new local development database."""
        db.create_all()
        print("Tabel database berhasil dibuat. Untuk perubahan berikutnya gunakan Flask-Migrate.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Create the predefined program-study list and active demo semester."""
        from datetime import date
        from sqlalchemy import or_
        from .models import StudyProgram, Semester
        db.create_all()
        programs = DEMO_STUDY_PROGRAMS
        for code, name in programs:
            existing = StudyProgram.query.filter(or_(StudyProgram.code == code, StudyProgram.name == name)).first()
            if not existing:
                db.session.add(StudyProgram(
                    code=code, name=name,
                    faculty="Universitas Teknokrat Indonesia", is_active=True
                ))
        semester = Semester.query.filter_by(name="Ganjil 2026/2027").first()
        if not semester:
            semester = Semester(name="Ganjil 2026/2027", academic_year="2026/2027", term="Ganjil",
                                start_date=date(2026, 8, 1), end_date=date(2027, 1, 31),
                                is_active=True, enrollment_open=True)
            db.session.add(semester)
        elif not Semester.query.filter_by(is_active=True).first():
            semester.is_active = True
        db.session.commit()
        print(f"Data demo berhasil disiapkan: {len(programs)} program studi dan semester aktif.")

    @app.cli.command("check-schema")
    def check_schema_command():
        """Compare the connected database tables/columns with current SQLAlchemy models."""
        import click
        from sqlalchemy import inspect

        with app.app_context():
            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            missing_tables = []
            missing_columns = []
            for table_name, table in db.metadata.tables.items():
                if table_name not in existing_tables:
                    missing_tables.append(table_name)
                    continue
                existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
                for column in table.columns:
                    if column.name not in existing_columns:
                        missing_columns.append(f"{table_name}.{column.name}")

            if not missing_tables and not missing_columns:
                click.echo("OK: tabel dan kolom database sesuai dengan model aplikasi saat ini.")
                return

            click.echo("Database belum sesuai dengan model aplikasi saat ini.")
            if missing_tables:
                click.echo("Tabel yang belum ada:")
                for name in missing_tables:
                    click.echo(f"  - {name}")
            if missing_columns:
                click.echo("Kolom yang belum ada:")
                for name in missing_columns:
                    click.echo(f"  - {name}")
            click.echo("Buat backup terlebih dahulu. Untuk database lama, gunakan migrasi yang ditinjau; init-db/create_all tidak menambahkan kolom ke tabel yang sudah ada.")
            raise click.ClickException("Pemeriksaan skema menemukan perbedaan.")

    @app.cli.command("create-admin")
    def create_admin_command():
        """Create an admin account interactively."""
        import click
        from .models import User
        name = click.prompt("Nama admin")
        email = click.prompt("Email admin").strip().lower()
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        if User.query.filter_by(email=email).first():
            click.echo("Email sudah terdaftar.")
            return
        if len(password) < 8:
            click.echo("Password minimal 8 karakter.")
            return
        user = User(full_name=name, email=email, role="admin", active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo("Akun Admin berhasil dibuat.")

    return app
