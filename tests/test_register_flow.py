import pytest

from app import create_app
from app.extensions import db
from app.integrations.base import ProviderUnavailable
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
        user = User(full_name="Sudah Ada", email="sudah@test.local", npm="23312001",
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
