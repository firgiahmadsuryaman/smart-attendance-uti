import pytest

from app import DEMO_STUDY_PROGRAMS
from app.integrations.base import (
    IdentityNotFound,
    ProviderUnavailable,
    status_label,
    status_tone,
)
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
