from .base import Identity, IdentityNotFound, IdentityProvider, ProviderUnavailable

UNAVAILABLE_TRIGGER = "99999999"

SAMPLE_STUDENTS = {
    "23312001": {
        "name": "Ayu Lestari",
        "program_name": "Informatika",
        "program_code": "IF",
        "faculty": "Fakultas Teknik dan Ilmu Komputer",
        "semester": 5,
        "cohort": "2023",
        "academic_status": "ACTIVE",
    },
    "23312002": {
        "name": "Bagus Prakoso",
        "program_name": "Informatika",
        "program_code": "IF",
        "faculty": "Fakultas Teknik dan Ilmu Komputer",
        "semester": 9,
        "cohort": "2021",
        "academic_status": "GRADUATED",
    },
    "23312003": {
        "name": "Citra Maharani",
        "program_name": "Teknik Robotika",
        "program_code": "TRB",
        "faculty": "Fakultas Teknik dan Ilmu Komputer",
        "semester": 3,
        "cohort": "2024",
        "academic_status": "ACTIVE",
        "expects_unregistered_program": True,
    },
    # Data uji yang diminta pemilik proyek; hanya aktif pada IDENTITY_PROVIDER=sample.
    "23312237": {
        "name": "Firgi Ahmad Suryaman",
        "program_name": "Informatika",
        "program_code": "IF",
        "faculty": "Fakultas Teknik dan Ilmu Komputer",
        "semester": 7,
        "cohort": "2023",
        "academic_status": "ACTIVE",
    },
}

SAMPLE_LECTURERS = {
    "0012345678": {
        "name": "Dr. Dwi Handayani",
        "program_name": "Informatika",
        "program_code": "IF",
        "faculty": "Fakultas Teknik dan Ilmu Komputer",
        "semester": None,
        "cohort": None,
        "academic_status": "ACTIVE",
        "nidn": "0212345678",
        "positions": ("Kepala Program Studi Informatika",),
    },
}


def _build(kind, identifier, data):
    return Identity(
        kind=kind,
        identifier=identifier,
        name=data["name"],
        program_name=data.get("program_name"),
        program_code=data.get("program_code"),
        faculty=data.get("faculty"),
        semester=data.get("semester"),
        cohort=data.get("cohort"),
        academic_status=(data.get("academic_status") or "UNKNOWN").upper(),
        nidn=data.get("nidn"),
        positions=tuple(data.get("positions") or ()),
    )


class SampleIdentityProvider(IdentityProvider):
    """Provider data contoh untuk pengembangan. Bukan data resmi kampus."""

    source_code = "SAMPLE"

    def resolve_student(self, npm):
        npm = (npm or "").strip()
        if npm == UNAVAILABLE_TRIGGER:
            raise ProviderUnavailable("sample: gangguan disimulasikan")
        data = SAMPLE_STUDENTS.get(npm)
        if data is None:
            raise IdentityNotFound("NPM", npm)
        return _build("student", npm, data)

    def resolve_lecturer(self, nik):
        nik = (nik or "").strip()
        if nik == UNAVAILABLE_TRIGGER:
            raise ProviderUnavailable("sample: gangguan disimulasikan")
        data = SAMPLE_LECTURERS.get(nik)
        if data is None:
            raise IdentityNotFound("NIK", nik)
        return _build("lecturer", nik, data)
