import pytest

from app import create_app
from app.blueprints.auth import _match_program
from app.extensions import db
from app.integrations.base import Identity, ProviderUnavailable
from app.models import StudyProgram, User
from app.utils import reset_rate_limit


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
        "IDENTITY_PROVIDER": "sample",
        "IDENTITY_CHECK_RATE_LIMIT": 0,
    })
    with app.app_context():
        db.create_all()
        db.session.add(StudyProgram(name="Informatika", code="IF",
                                    faculty="Fakultas Teknik dan Ilmu Komputer"))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def clean_rate_limit():
    reset_rate_limit()
    yield
    reset_rate_limit()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_check_returns_card_with_provider_name(client):
    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312001"})

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "Ayu Lestari" in response.get_data(as_text=True)
    assert "Informatika" in response.get_data(as_text=True)


def test_check_returns_requested_firgi_sample_identity(client):
    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312237"})

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Firgi Ahmad Suryaman" in body
    assert "Informatika" in body


def test_registration_stores_requested_firgi_sample_identity(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312237",
        email="firgi.sample@example.test", password="uji-firgi-123",
        password_confirm="uji-firgi-123",
    )

    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(npm="23312237").one()
        assert user.full_name == "Firgi Ahmad Suryaman"
        assert user.program.code == "IF"
        assert user.program.faculty == "Fakultas Teknik dan Ilmu Komputer"
        assert user.cohort == "2023"
        assert user.identity_source == "SAMPLE"


def test_check_unknown_identifier_returns_not_found_message(client):
    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "00000000"})

    body = response.get_data(as_text=True)
    assert "tidak ditemukan" in body
    assert response.status_code == 404


def test_check_unavailable_provider_message_differs_from_not_found(client):
    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "99999999"})

    body = response.get_data(as_text=True)
    assert "tidak dapat dihubungi" in body
    assert "tidak ditemukan" not in body
    assert response.status_code == 503


def test_check_rejects_non_numeric_identifier(client):
    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "abc!!"})

    assert response.status_code == 400
    assert "tidak valid" in response.get_data(as_text=True)


def test_check_lecturer_returns_nidn_and_positions(client):
    response = client.post("/register/check", data={"jenis": "dosen", "nik": "0012345678"})

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Dwi Handayani" in body
    assert "0212345678" in body
    assert "Kepala Program Studi Informatika" in body


def test_check_reports_unregistered_program_as_blocked(client):
    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312003"})

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Citra Maharani" in body
    assert "belum terdaftar" in body


def test_check_reports_inactive_status_as_blocked(client):
    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312002"})

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Lulus" in body
    assert "belum dapat dibuat" in body


def test_check_flags_already_registered_identifier(app, client):
    with app.app_context():
        user = User(full_name="Sudah Ada", email="sudah@example.com", npm="23312001",
                    role="student", active=True)
        user.set_password("password-uji-123")
        db.session.add(user)
        db.session.commit()

    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312001"})

    assert "sudah terdaftar" in response.get_data(as_text=True)


def test_check_is_rate_limited_after_limit_reached(app, client):
    app.config["IDENTITY_CHECK_RATE_LIMIT"] = 3
    for _ in range(3):
        client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312001"})

    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312001"})

    assert response.status_code == 429
    assert "Terlalu banyak pemeriksaan" in response.get_data(as_text=True)


def test_rate_limited_request_does_not_crash_with_invalid_identifier(app, client):
    app.config["IDENTITY_CHECK_RATE_LIMIT"] = 1
    client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312001"})

    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "!!!bad!!!"})

    assert response.status_code == 429


def test_check_matches_inactive_program_by_name_and_code(app, client):
    # 1. Program tidak aktif tetap cocok berdasarkan nama saat kode berbeda/tidak cocok
    with app.app_context():
        prog_name = StudyProgram(
            name="Teknik Robotika",
            code="TRB_DIFF",
            faculty="Fakultas Teknik dan Ilmu Komputer",
            is_active=False,
        )
        db.session.add(prog_name)
        db.session.commit()

        matched_direct_name = _match_program(Identity(
            kind="student",
            identifier="23312003",
            name="Citra Maharani",
            program_name="Teknik Robotika",
            program_code=None,
            academic_status="ACTIVE",
        ))
        assert matched_direct_name is not None
        assert matched_direct_name.id == prog_name.id

    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312003"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Citra Maharani" in body
    assert "belum terdaftar" not in body

    # 2. Program tidak aktif juga tetap cocok berdasarkan kode
    with app.app_context():
        db.session.delete(db.session.get(StudyProgram, prog_name.id))
        prog_code = StudyProgram(
            name="Nama Lain di Database",
            code="TRB",
            faculty="Fakultas Teknik dan Ilmu Komputer",
            is_active=False,
        )
        db.session.add(prog_code)
        db.session.commit()

        matched_direct_code = _match_program(Identity(
            kind="student",
            identifier="23312003",
            name="Citra Maharani",
            program_name=None,
            program_code="TRB",
            academic_status="ACTIVE",
        ))
        assert matched_direct_code is not None
        assert matched_direct_code.id == prog_code.id

    response = client.post("/register/check", data={"jenis": "mahasiswa", "npm": "23312003"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Citra Maharani" in body
    assert "belum terdaftar" not in body


def _register(client, path, **fields):
    return client.post(path, data=fields)


def test_student_registration_uses_provider_identity(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="ayu@example.com", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(npm="23312001").one()
        assert user.role == "student"
        assert user.full_name == "Ayu Lestari"
        assert user.cohort == "2023"
        assert user.identity_source == "SAMPLE"
        assert user.program.code == "IF"


def test_forged_identity_fields_in_form_are_ignored(app, client):
    _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="palsu@example.com", password="rahasia-123", password_confirm="rahasia-123",
        full_name="Nama Palsu", program_id="9999", cohort="1900",
    )

    with app.app_context():
        user = User.query.filter_by(npm="23312001").one()
        assert user.full_name == "Ayu Lestari"
        assert user.cohort == "2023"
        assert user.program.code == "IF"


def test_lecturer_registration_stores_nik_and_nidn(app, client):
    _register(
        client, "/register/lecturer",
        jenis="dosen", nik="0012345678",
        email="dwi@example.com", password="rahasia-123", password_confirm="rahasia-123",
    )

    with app.app_context():
        user = User.query.filter_by(employee_id="0012345678").one()
        assert user.role == "lecturer"
        assert user.npm is None
        assert user.nidn == "0212345678"
        assert user.full_name == "Dr. Dwi Handayani"


def test_sending_both_identifiers_only_creates_the_active_pane_account(app, client):
    _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001", nik="0012345678",
        email="ganda@example.com", password="rahasia-123", password_confirm="rahasia-123",
    )

    with app.app_context():
        assert User.query.filter_by(email="ganda@example.com").count() == 1
        assert User.query.filter_by(employee_id="0012345678").count() == 0


def test_inactive_status_is_rejected_at_creation(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312002",
        email="lulus@example.com", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 422
    with app.app_context():
        assert User.query.filter_by(email="lulus@example.com").count() == 0


def test_unregistered_program_is_rejected_at_creation(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312003",
        email="robot@example.com", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 422
    with app.app_context():
        assert User.query.filter_by(email="robot@example.com").count() == 0


def test_duplicate_email_is_rejected_without_touching_existing_account(app, client):
    with app.app_context():
        existing = User(full_name="Pemilik Lama", email="ayu@example.com", npm="20999999",
                        role="student", active=True)
        existing.set_password("password-uji-123")
        db.session.add(existing)
        db.session.commit()

    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="ayu@example.com", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 400
    with app.app_context():
        assert User.query.filter_by(email="ayu@example.com").count() == 1
        assert User.query.filter_by(email="ayu@example.com").one().full_name == "Pemilik Lama"
        assert User.query.filter_by(npm="23312001").count() == 0


def test_duplicate_identifier_is_rejected(app, client):
    with app.app_context():
        existing = User(full_name="Sudah Ada", email="lama@example.com", npm="23312001",
                        role="student", active=True)
        existing.set_password("password-uji-123")
        db.session.add(existing)
        db.session.commit()

    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="baru@example.com", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 400
    with app.app_context():
        assert User.query.filter_by(email="baru@example.com").count() == 0


def test_password_mismatch_is_rejected(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="ayu@example.com", password="rahasia-123", password_confirm="beda-123",
    )

    assert response.status_code == 400
    with app.app_context():
        assert User.query.filter_by(email="ayu@example.com").count() == 0


def test_short_password_is_rejected(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="ayu@example.com", password="pendek", password_confirm="pendek",
    )

    assert response.status_code == 400


def test_unknown_identifier_is_rejected_at_creation(app, client):
    """Pemeriksaan ulang saat pembuatan akun tetap wajib, walau form dikirim langsung."""
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="00000000",
        email="hantu@example.com", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 404
    with app.app_context():
        assert User.query.filter_by(email="hantu@example.com").count() == 0


def test_invalid_email_format_is_rejected(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="bukan-email", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 400
    with app.app_context():
        assert User.query.filter_by(npm="23312001").count() == 0


def test_legacy_post_register_returns_405_and_creates_no_user(app, client):
    """POST ke /register lama harus ditolak 405 dan tidak membuat akun."""
    with app.app_context():
        program = StudyProgram.query.filter_by(code="IF").one()
        program_id = program.id
        initial_user_count = User.query.count()

    response = client.post("/register", data={
        "npm": "99999999",
        "full_name": "Pengguna Ilegal",
        "email": "ilegal@example.com",
        "password": "password123",
        "program_id": program_id,
        "cohort": "2024",
    })

    assert response.status_code == 405
    with app.app_context():
        assert User.query.filter_by(email="ilegal@example.com").count() == 0
        assert User.query.filter_by(npm="99999999").count() == 0
        assert User.query.count() == initial_user_count


