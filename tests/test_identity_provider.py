import pytest

from app import DEMO_STUDY_PROGRAMS
from app.integrations.base import (
    IdentityNotFound,
    ProviderMisconfigured,
    ProviderUnavailable,
    status_label,
    status_tone,
)
from app.integrations.pustik import PustikIdentityProvider
from app.integrations.sample import (
    SAMPLE_LECTURERS,
    SAMPLE_STUDENTS,
    UNAVAILABLE_TRIGGER,
    SampleIdentityProvider,
)


@pytest.fixture()
def provider():
    return SampleIdentityProvider()


def test_resolve_student_returns_complete_identity(provider):
    identity = provider.resolve_student("23312001")

    assert identity.kind == "student"
    assert identity.identifier == "23312001"
    assert identity.name == "Ayu Lestari"
    assert identity.program_name == "Informatika"
    assert identity.program_code == "IF"
    assert identity.semester == 5
    assert identity.cohort == "2023"
    assert identity.academic_status == "ACTIVE"
    assert identity.is_active is True
    assert identity.role == "student"
    assert provider.source_code == "SAMPLE"


def test_resolve_lecturer_returns_nidn_and_positions(provider):
    identity = provider.resolve_lecturer("0012345678")

    assert identity.kind == "lecturer"
    assert identity.nidn == "0212345678"
    assert identity.positions == ("Kepala Program Studi Informatika",)
    assert identity.role == "lecturer"


def test_unknown_student_raises_not_found(provider):
    with pytest.raises(IdentityNotFound) as excinfo:
        provider.resolve_student("00000000")

    assert "NPM" in excinfo.value.user_message
    assert "tidak ditemukan" in excinfo.value.user_message


def test_unknown_lecturer_raises_not_found_with_nik_label(provider):
    with pytest.raises(IdentityNotFound) as excinfo:
        provider.resolve_lecturer("0000000000")

    assert "NIK" in excinfo.value.user_message


def test_trigger_identifier_simulates_outage(provider):
    with pytest.raises(ProviderUnavailable):
        provider.resolve_student(UNAVAILABLE_TRIGGER)


def test_sample_programs_exist_in_seed_list():
    """Data contoh tidak boleh lepas dari daftar program studi seed-demo."""
    seeded_codes = {code for code, _ in DEMO_STUDY_PROGRAMS}
    seeded_names = {name for _, name in DEMO_STUDY_PROGRAMS}

    for npm, data in SAMPLE_STUDENTS.items():
        if data.get("expects_unregistered_program"):
            continue
        assert data["program_code"] in seeded_codes, f"kode prodi {npm} tidak ada di seed"
        assert data["program_name"] in seeded_names, f"nama prodi {npm} tidak ada di seed"

    for nik, data in SAMPLE_LECTURERS.items():
        if data.get("expects_unregistered_program"):
            continue
        assert data["program_code"] in seeded_codes, f"kode prodi {nik} tidak ada di seed"
        assert data["program_name"] in seeded_names, f"nama prodi {nik} tidak ada di seed"


def test_negative_sample_entry_points_to_unregistered_program():
    """Entri kasus negatif harus benar-benar tidak ada di seed."""
    seeded_codes = {code for code, _ in DEMO_STUDY_PROGRAMS}
    negative = SAMPLE_STUDENTS["23312003"]

    assert negative["expects_unregistered_program"] is True
    assert negative["program_code"] not in seeded_codes


def test_status_labels_and_tones_cover_all_known_statuses():
    assert status_label("ACTIVE") == "Aktif"
    assert status_label("GRADUATED") == "Lulus"
    assert status_tone("ACTIVE") == "success"
    assert status_tone("DROPPED_OUT") == "danger"
    assert status_label("SESUATU_YANG_ANE") == "Status belum dikenali"
    assert status_tone("SESUATU_YANG_ANE") == "neutral"


def _transport_returning(status, body):
    def transport(url, payload, headers, timeout):
        return status, body
    return transport


def _transport_raising(exc):
    def transport(url, payload, headers, timeout):
        raise exc
    return transport


def test_pustik_requires_base_url():
    provider = PustikIdentityProvider(base_url="")

    with pytest.raises(ProviderMisconfigured):
        provider.resolve_student("23312001")


def test_pustik_maps_response_into_identity():
    body = {
        "ok": True,
        "data": {
            "identity": {
                "npm": "23312001",
                "name": "Ayu Lestari",
                "programStudy": {"name": "Informatika", "code": "IF"},
                "faculty": {"name": "Fakultas Teknik dan Ilmu Komputer"},
                "semester": 5,
                "cohort": "2023",
                "academicStatus": "aktif",
            }
        },
    }
    provider = PustikIdentityProvider(
        base_url="https://pustik.example/api",
        transport=_transport_returning(200, body),
    )

    identity = provider.resolve_student("23312001")

    assert identity.name == "Ayu Lestari"
    assert identity.program_name == "Informatika"
    assert identity.program_code == "IF"
    assert identity.faculty == "Fakultas Teknik dan Ilmu Komputer"
    assert identity.semester == 5
    assert identity.academic_status == "AKTIF"
    assert provider.source_code == "PUSTIK_API"


def test_pustik_tolerates_string_program_and_missing_faculty():
    body = {"data": {"name": "Ayu Lestari", "programStudy": "Informatika"}}
    provider = PustikIdentityProvider(
        base_url="https://pustik.example/api",
        transport=_transport_returning(200, body),
    )

    identity = provider.resolve_student("23312001")

    assert identity.program_name == "Informatika"
    assert identity.faculty is None
    assert identity.semester is None
    assert identity.academic_status == "UNKNOWN"


def test_pustik_404_is_not_found():
    provider = PustikIdentityProvider(
        base_url="https://pustik.example/api",
        transport=_transport_returning(404, {"message": "tidak ada"}),
    )

    with pytest.raises(IdentityNotFound):
        provider.resolve_student("00000000")


def test_pustik_5xx_is_unavailable():
    provider = PustikIdentityProvider(
        base_url="https://pustik.example/api",
        transport=_transport_returning(503, None),
    )

    with pytest.raises(ProviderUnavailable):
        provider.resolve_student("23312001")


def test_pustik_transport_error_is_unavailable():
    provider = PustikIdentityProvider(
        base_url="https://pustik.example/api",
        transport=_transport_raising(TimeoutError("koneksi habis")),
    )

    with pytest.raises(ProviderUnavailable):
        provider.resolve_student("23312001")


def test_pustik_unmappable_body_is_unavailable():
    provider = PustikIdentityProvider(
        base_url="https://pustik.example/api",
        transport=_transport_returning(200, {"data": {"npm": "23312001"}}),
    )

    with pytest.raises(ProviderUnavailable):
        provider.resolve_student("23312001")


from app import create_app
from app.integrations import build_identity_provider, identity_provider_is_sample


def test_factory_builds_sample_provider_by_default():
    provider = build_identity_provider({})

    assert provider.source_code == "SAMPLE"


def test_factory_builds_pustik_provider_from_config():
    provider = build_identity_provider(
        {"IDENTITY_PROVIDER": "pustik", "PUSTIK_BASE_URL": "https://pustik.example/api"}
    )

    assert provider.source_code == "PUSTIK_API"
    assert provider.base_url == "https://pustik.example/api"


def test_factory_rejects_unknown_provider_name():
    with pytest.raises(ProviderMisconfigured):
        build_identity_provider({"IDENTITY_PROVIDER": "entah"})


def test_identity_provider_is_sample_flag():
    assert identity_provider_is_sample({}) is True
    assert identity_provider_is_sample({"IDENTITY_PROVIDER": "pustik"}) is False


def test_app_config_carries_identity_keys():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
    })

    assert app.config["IDENTITY_PROVIDER"] == "sample"
    assert app.config["IDENTITY_CHECK_RATE_LIMIT"] == 10
    assert "PUSTIK_BASE_URL" in app.config


def test_get_identity_provider_is_cached_per_app():
    from app.integrations import get_identity_provider

    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        assert get_identity_provider() is get_identity_provider()


