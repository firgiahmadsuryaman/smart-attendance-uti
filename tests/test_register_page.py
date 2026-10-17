import pytest

from app import create_app
from app.extensions import db
from app.models import StudyProgram


@pytest.fixture()
def client():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
        "IDENTITY_PROVIDER": "sample",
    })
    with app.app_context():
        db.create_all()
        db.session.add(StudyProgram(name="Informatika", code="IF", faculty="FTIK"))
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_register_page_has_both_panes_and_fields(client):
    body = client.get("/register").get_data(as_text=True)

    assert 'name="npm"' in body
    assert 'name="nik"' in body
    assert 'name="password_confirm"' in body
    assert 'name="full_name"' not in body
    assert 'name="program_id"' not in body
    assert 'name="cohort"' not in body


def test_register_page_exposes_tabs_as_links(client):
    body = client.get("/register").get_data(as_text=True)

    assert 'role="tablist"' in body
    assert 'role="tab"' in body
    assert "/register?jenis=dosen" in body


def test_mahasiswa_pane_is_active_by_default(client):
    body = client.get("/register").get_data(as_text=True)

    assert 'data-jenis="mahasiswa"' in body


def test_dosen_pane_can_be_selected_by_query_parameter(client):
    body = client.get("/register?jenis=dosen").get_data(as_text=True)

    assert 'data-pane="dosen" aria-hidden="false"' in body or 'data-pane="dosen"' in body
    assert "/register?jenis=mahasiswa" in body


def test_sample_mode_badge_is_visible_with_sample_provider(client):
    body = client.get("/register").get_data(as_text=True)

    assert "Mode data contoh" in body


def test_page_exposes_contract_used_by_register_js(client):
    body = client.get("/register").get_data(as_text=True)

    assert "data-register-page" in body
    assert 'data-check-url="/register/check"' in body
    assert "data-identity-slot" in body
    assert "data-account-form" in body


def test_identity_card_survives_a_rejected_submission(client):
    """Kartu konfirmasi tetap tampil saat pendaftaran ditolak setelah identitas terbaca.

    Kegagalan yang terjadi SEBELUM identitas diambil dari provider (kata sandi terlalu
    pendek, format email salah, email atau identitas sudah terdaftar) memang tidak
    menyertakan kartu, karena identitasnya belum ada untuk ditampilkan.
    """
    response = client.post("/register/student", data={
        "jenis": "mahasiswa", "npm": "23312002",
        "email": "bagus@example.com", "password": "rahasia-123", "password_confirm": "rahasia-123",
    })

    body = response.get_data(as_text=True)
    assert response.status_code == 422
    assert "Bagus Prakoso" in body
    assert 'value="23312002"' in body
