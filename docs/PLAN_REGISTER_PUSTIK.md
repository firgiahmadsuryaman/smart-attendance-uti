# Rencana Implementasi: Integrasi Identitas PUSTIK & Halaman Register Baru

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mahasiswa dan dosen mendaftar dengan NPM/NIK yang diverifikasi ke provider identitas (data contoh sekarang, PUSTIK nanti), sehingga nama, program studi, dan angkatan berasal dari sumber resmi.

**Architecture:** Paket `app/integrations/` berisi satu antarmuka `IdentityProvider` dengan dua implementasi yang dapat ditukar lewat konfigurasi. Blueprint `auth` memakai provider itu, memetakan hasilnya ke tabel lokal, dan membangun akun dari hasil provider — bukan dari isian form. Halaman register memakai dua panel tab dan memuat kartu konfirmasi identitas dari partial Jinja yang sama, baik lewat AJAX maupun saat halaman dirender ulang.

**Tech Stack:** Flask 3, Flask-SQLAlchemy, Flask-WTF (CSRF), Flask-Migrate, Jinja2, `requests`, pytest.

**Spec:** `docs/SPEC_REGISTER_PUSTIK.md`

## Global Constraints

- Python 3.10–3.12. `requirements-face.txt` mematok `mediapipe==0.10.35` yang belum punya wheel untuk Python 3.13 ke atas.
- Dependensi baru: `requests>=2.31,<3.0` di `requirements.txt`. Tidak ada dependensi lain.
- Bahasa: seluruh teks antarmuka, pesan galat, komentar kode, dan nama berkas dokumentasi memakai Bahasa Indonesia. Nama kelas, fungsi, dan variabel memakai Bahasa Inggris.
- `app/integrations/base.py` tidak boleh mengimpor Flask maupun model database.
- Paket `app/integrations/` tidak boleh memanggil `db.session`.
- IDENTIFIER hanya angka, 4–20 karakter.
- Hanya status `ACTIVE` yang boleh membuat akun.
- Server tidak pernah mempercayai `full_name`, `program_id`, atau `cohort` dari form.
- Setiap commit memakai trailer:
  `git commit -m "..." -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"`
- Perintah pengujian memakai virtualenv proyek: `.venv/bin/python -m pytest`.
- Perintah Flask memakai `.venv/bin/python -m flask --app run.py`.

## Review Focus

Kelima hal berikut tidak dijamin tertutup oleh pengujian biasa di tiap task, dan paling mungkin menggigit orang yang memakai aplikasi ini. Setiap baris punya pengujiannya di task pemilik kode.

1. **NPM/NIK berisi huruf, tanda baca, atau spasi** — pengguna salah ketik. Harus ditolak dengan pesan yang bisa dipahami, bukan error 500. (Task 6)
2. **Bentuk respons provider berbeda dari dugaan** — `programStudy` berupa string, `faculty` tidak ada, `semester` berupa string. Harus tetap menghasilkan `Identity` yang wajar atau `ProviderUnavailable`, bukan crash. (Task 2)
3. **Kedua panel tab ada di DOM bersamaan** — mengirim `npm` dan `nik` sekaligus tidak boleh membuat dua akun atau memilih panel yang tidak aktif. (Task 7)
4. **Tombol Cek ditekan berulang cepat** — pembatas laju menjawab dengan pesan pembatasan, bukan 500, dan tidak mengunci pengguna selamanya setelah satu menit lewat. (Task 6)
5. **Email sudah dipakai akun lama sementara NPM valid** — ditolak dengan pesan email yang sudah terdaftar, tidak membuat akun ganda atau menimpa akun lama. (Task 7)

---

## Task 1: Kontrak provider dan provider data contoh

**Files:**
- Create: `app/integrations/__init__.py` (kosong pada task ini)
- Create: `app/integrations/base.py`
- Create: `app/integrations/sample.py`
- Modify: `app/__init__.py:121-161` (angkat daftar program studi ke tingkat modul)
- Test: `tests/test_identity_provider.py`

**Interfaces:**
- Consumes: tidak ada.
- Produces: `Identity` (dataclass), `IdentityError`, `IdentityNotFound(label, identifier)`, `ProviderUnavailable(detail)`, `ProviderMisconfigured(detail)`, `ProgramNotRegistered(detail)`, `IdentityNotActive(status)`, `STATUS_LABELS`, `STATUS_TONES`, `status_label(status)`, `status_tone(status)`, `IdentityProvider` (ABC dengan `source_code`, `resolve_student(npm)`, `resolve_lecturer(nik)`), `SampleIdentityProvider`, `SAMPLE_STUDENTS`, `SAMPLE_LECTURERS`, `UNAVAILABLE_TRIGGER`, serta `DEMO_STUDY_PROGRAMS` di `app/__init__.py`.

- [ ] **Step 1: Angkat daftar program studi demo ke tingkat modul**

`app/__init__.py` saat ini menaruh daftar 15 program studi sebagai variabel lokal di dalam `seed_demo_command`, sehingga tidak dapat diimpor pengujian. Pindahkan ke tingkat modul, di atas `create_app`:

```python
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
```

Lalu di dalam `seed_demo_command`, ganti blok `programs = [...]` dan `for code, name in programs:` menjadi:

```python
        programs = DEMO_STUDY_PROGRAMS
        for code, name in programs:
```

- [ ] **Step 2: Tulis kontrak provider**

Buat `app/integrations/__init__.py` sebagai berkas kosong untuk task ini.

Buat `app/integrations/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

STATUS_LABELS = {
    "ACTIVE": "Aktif",
    "LEAVE": "Sedang cuti",
    "GRADUATED": "Lulus",
    "INACTIVE": "Tidak aktif",
    "TRANSFERRED": "Pindah",
    "DROPPED_OUT": "Berhenti",
    "RESIGNED": "Mengundurkan diri",
    "UNVERIFIED": "Belum terverifikasi",
    "UNKNOWN": "Belum dapat diverifikasi",
}

STATUS_TONES = {
    "ACTIVE": "success",
    "LEAVE": "warning",
    "UNVERIFIED": "neutral",
    "UNKNOWN": "neutral",
    "DROPPED_OUT": "danger",
    "RESIGNED": "danger",
    "GRADUATED": "info",
    "TRANSFERRED": "info",
}


def status_label(status):
    return STATUS_LABELS.get((status or "").upper(), "Status belum dikenali")


def status_tone(status):
    return STATUS_TONES.get((status or "").upper(), "neutral")


class IdentityError(Exception):
    """Kegagalan pemeriksaan identitas yang punya pesan siap tampil."""

    user_message = "Terjadi kesalahan saat memeriksa identitas."

    def __init__(self, detail=""):
        super().__init__(detail or self.user_message)
        self.detail = detail


class IdentityNotFound(IdentityError):
    def __init__(self, label, identifier=""):
        self.label = label
        self.identifier = identifier
        super().__init__(f"{label} {identifier} tidak ditemukan".strip())
        self.user_message = f"{label} tidak ditemukan di data akademik universitas."


class ProviderUnavailable(IdentityError):
    user_message = "Sistem data akademik sedang tidak dapat dihubungi. Coba beberapa saat lagi."


class ProviderMisconfigured(IdentityError):
    user_message = "Integrasi data akademik belum dikonfigurasi. Hubungi administrator."


class ProgramNotRegistered(IdentityError):
    user_message = "Program studi Anda belum terdaftar di sistem. Hubungi administrator."


class IdentityNotActive(IdentityError):
    def __init__(self, status):
        self.status = (status or "UNKNOWN").upper()
        super().__init__(f"status={self.status}")
        self.user_message = (
            f"Status akademik Anda: {status_label(self.status)}. Akun belum dapat dibuat."
        )


@dataclass(frozen=True)
class Identity:
    kind: str
    identifier: str
    name: str
    program_name: str | None = None
    program_code: str | None = None
    faculty: str | None = None
    semester: int | None = None
    cohort: str | None = None
    academic_status: str = "UNKNOWN"
    nidn: str | None = None
    positions: tuple[str, ...] = ()

    @property
    def is_active(self):
        return self.academic_status == "ACTIVE"

    @property
    def role(self):
        return "lecturer" if self.kind == "lecturer" else "student"


class IdentityProvider(ABC):
    source_code = "UNKNOWN"

    @abstractmethod
    def resolve_student(self, npm):
        raise NotImplementedError

    @abstractmethod
    def resolve_lecturer(self, nik):
        raise NotImplementedError
```

- [ ] **Step 3: Tulis provider data contoh**

Buat `app/integrations/sample.py`:

```python
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
```

- [ ] **Step 4: Tulis pengujian yang gagal**

Buat `tests/test_identity_provider.py`:

```python
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
```

- [ ] **Step 5: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_identity_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.integrations'`

- [ ] **Step 6: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_identity_provider.py -v`
Expected: PASS, 8 pengujian lulus.

- [ ] **Step 7: Pastikan pengujian lama tidak rusak**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 18 lulus (10 pengujian lama + 8 pengujian baru), tanpa kegagalan.

- [ ] **Step 8: Commit**

```bash
git add app/__init__.py app/integrations/ tests/test_identity_provider.py
git commit -m "feat: tambahkan kontrak provider identitas dan provider data contoh" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

---

## Task 2: Provider HTTP PUSTIK dengan transport yang dapat disuntikkan

**Files:**
- Create: `app/integrations/pustik.py`
- Test: `tests/test_identity_provider.py` (tambahan)

**Interfaces:**
- Consumes: `Identity`, `IdentityNotFound`, `ProviderMisconfigured`, `ProviderUnavailable`, `IdentityProvider` dari Task 1.
- Produces: `PustikIdentityProvider(base_url, api_key, timeout, transport=None, student_path="/auth/resolve/student", lecturer_path="/auth/resolve/lecturer")`, dengan `source_code == "PUSTIK_API"` dan atribut `_map_identity(kind, identifier, body)`.

Kontrak transport yang disuntikkan, dipakai juga oleh pengujian:

```python
def transport(url: str, payload: dict, headers: dict, timeout: int) -> tuple[int, dict | None]
```

**Catatan penting:** pemetaan di `_map_identity` ditulis atas dasar dugaan bentuk respons, diambil dari temuan di `docs/INTEGRASI_PUSTIK.md` bagian 3. Pemetaan wajib ditinjau ketika kontrak resmi PUSTIK tersedia.

- [ ] **Step 1: Tulis pengujian yang gagal**

Tambahkan ke `tests/test_identity_provider.py`:

```python
from app.integrations.base import ProviderMisconfigured
from app.integrations.pustik import PustikIdentityProvider


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
```

- [ ] **Step 2: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_identity_provider.py -v -k pustik`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.integrations.pustik'`

- [ ] **Step 3: Tulis implementasi**

Buat `app/integrations/pustik.py`:

```python
import logging

from .base import (
    Identity,
    IdentityNotFound,
    IdentityProvider,
    ProviderMisconfigured,
    ProviderUnavailable,
)

logger = logging.getLogger(__name__)


def _as_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _name_of(value):
    if isinstance(value, dict):
        return value.get("name")
    if isinstance(value, str):
        return value or None
    return None


class PustikIdentityProvider(IdentityProvider):
    """Klien identitas PUSTIK.

    Pemetaan respons di `_map_identity` ditulis atas dasar dugaan bentuk dan
    wajib ditinjau ketika kontrak resmi tersedia. Lihat docs/INTEGRASI_PUSTIK.md.
    """

    source_code = "PUSTIK_API"

    def __init__(self, base_url="", api_key="", timeout=8, transport=None,
                 student_path="/auth/resolve/student", lecturer_path="/auth/resolve/lecturer"):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.api_key = (api_key or "").strip()
        self.timeout = timeout or 8
        self.student_path = student_path
        self.lecturer_path = lecturer_path
        self._transport = transport or self._default_transport

    def _default_transport(self, url, payload, headers, timeout):
        import requests

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            raise ProviderUnavailable(str(exc)) from exc
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, None

    def resolve_student(self, npm):
        identifier = (npm or "").strip()
        return self._resolve(self.student_path, {"npm": identifier}, "student", "NPM", identifier)

    def resolve_lecturer(self, nik):
        identifier = (nik or "").strip()
        return self._resolve(self.lecturer_path, {"nik": identifier}, "lecturer", "NIK", identifier)

    def _resolve(self, path, payload, kind, label, identifier):
        if not self.base_url:
            raise ProviderMisconfigured("PUSTIK_BASE_URL kosong")

        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            status, body = self._transport(url, payload, headers, self.timeout)
        except ProviderUnavailable:
            raise
        except Exception as exc:
            logger.warning("PUSTIK tidak dapat dihubungi (%s): %s", url, exc)
            raise ProviderUnavailable(str(exc)) from exc

        if status == 404:
            raise IdentityNotFound(label, identifier)
        if status >= 500 or body is None:
            logger.warning("PUSTIK membalas status %s untuk %s", status, url)
            raise ProviderUnavailable(f"status {status}")
        if status >= 400:
            if self._looks_not_found(body):
                raise IdentityNotFound(label, identifier)
            logger.warning("PUSTIK menolak permintaan (%s) untuk %s", status, url)
            raise ProviderUnavailable(f"status {status}")
        if self._looks_not_found(body):
            raise IdentityNotFound(label, identifier)

        return self._map_identity(kind, identifier, body)

    @staticmethod
    def _looks_not_found(body):
        if not isinstance(body, dict):
            return False
        if body.get("ok") is False:
            return True
        error = body.get("error")
        if isinstance(error, dict) and error.get("code") in {
            "NOT_FOUND", "BAD_REQUEST",
        }:
            return True
        return False

    @staticmethod
    def _map_identity(kind, identifier, body):
        data = body if isinstance(body, dict) else {}
        raw = data.get("identity") or data.get("data") or data
        if not isinstance(raw, dict):
            raise ProviderUnavailable("bentuk respons tidak dikenali")

        name = (raw.get("name") or "").strip()
        if not name:
            raise ProviderUnavailable("respons tidak memuat nama")

        program = raw.get("programStudy") or raw.get("studyProgram")
        program_code = raw.get("programCode")
        if isinstance(program, dict) and not program_code:
            program_code = program.get("code")

        positions = raw.get("positions") or ()
        if isinstance(positions, str):
            positions = (positions,)

        cohort = raw.get("cohort")

        return Identity(
            kind=kind,
            identifier=identifier,
            name=name,
            program_name=_name_of(program),
            program_code=program_code,
            faculty=_name_of(raw.get("faculty")),
            semester=_as_int(raw.get("semester")),
            cohort=str(cohort) if cohort not in (None, "") else None,
            academic_status=str(
                raw.get("academicStatus") or raw.get("academic_status") or "UNKNOWN"
            ).upper(),
            nidn=raw.get("nidn"),
            positions=tuple(str(item) for item in positions),
        )
```

- [ ] **Step 4: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_identity_provider.py -v`
Expected: PASS, seluruh pengujian lulus termasuk 7 pengujian `pustik` baru.

- [ ] **Step 5: Commit**

```bash
git add app/integrations/pustik.py tests/test_identity_provider.py
git commit -m "feat: tambahkan provider HTTP PUSTIK dengan transport yang dapat disuntikkan" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

---

## Task 3: Pabrik provider, konfigurasi, dan dependensi

**Files:**
- Modify: `app/integrations/__init__.py`
- Modify: `app/__init__.py:15-25` (kunci konfigurasi) dan setelah `return app` di `create_app`
- Modify: `requirements.txt`
- Modify: `.env.example`, `.env`
- Test: `tests/test_identity_provider.py` (tambahan)

**Interfaces:**
- Consumes: `SampleIdentityProvider` (Task 1), `PustikIdentityProvider` (Task 2).
- Produces: `build_identity_provider(config) -> IdentityProvider`, `get_identity_provider() -> IdentityProvider`, `identity_provider_is_sample(config) -> bool`. Kunci konfigurasi aplikasi: `IDENTITY_PROVIDER`, `PUSTIK_BASE_URL`, `PUSTIK_API_KEY`, `PUSTIK_TIMEOUT`, `IDENTITY_CHECK_RATE_LIMIT`.

- [ ] **Step 1: Tulis pengujian yang gagal**

Tambahkan ke `tests/test_identity_provider.py`:

```python
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
```

- [ ] **Step 2: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_identity_provider.py -v -k factory`
Expected: FAIL — `ImportError: cannot import name 'build_identity_provider'`

- [ ] **Step 3: Tulis pabrik provider**

Isi `app/integrations/__init__.py`:

```python
from flask import current_app

from .base import IdentityProvider, ProviderMisconfigured
from .pustik import PustikIdentityProvider
from .sample import SampleIdentityProvider

_PROVIDER_KEY = "identity_provider"


def provider_name(config):
    return (config.get("IDENTITY_PROVIDER") or "sample").strip().lower()


def identity_provider_is_sample(config):
    return provider_name(config) == "sample"


def build_identity_provider(config):
    name = provider_name(config)
    if name == "sample":
        return SampleIdentityProvider()
    if name == "pustik":
        return PustikIdentityProvider(
            base_url=config.get("PUSTIK_BASE_URL", ""),
            api_key=config.get("PUSTIK_API_KEY", ""),
            timeout=config.get("PUSTIK_TIMEOUT", 8),
        )
    raise ProviderMisconfigured(f"IDENTITY_PROVIDER tidak dikenal: {name}")


def get_identity_provider():
    cached = current_app.extensions.get(_PROVIDER_KEY)
    if cached is None:
        cached = build_identity_provider(current_app.config)
        current_app.extensions[_PROVIDER_KEY] = cached
    return cached
```

- [ ] **Step 4: Tambahkan kunci konfigurasi dan peringatan provider contoh**

Di `app/__init__.py`, di dalam `app.config.from_mapping(...)` pada `create_app`, tambahkan setelah baris `DEBUG=...`:

```python
        IDENTITY_PROVIDER=os.getenv("IDENTITY_PROVIDER", "sample"),
        PUSTIK_BASE_URL=os.getenv("PUSTIK_BASE_URL", ""),
        PUSTIK_API_KEY=os.getenv("PUSTIK_API_KEY", ""),
        PUSTIK_TIMEOUT=int(os.getenv("PUSTIK_TIMEOUT", "8")),
        IDENTITY_CHECK_RATE_LIMIT=int(os.getenv("IDENTITY_CHECK_RATE_LIMIT", "10")),
```

Lalu tepat sebelum `return app` di akhir `create_app`:

```python
    from .integrations import identity_provider_is_sample
    if identity_provider_is_sample(app.config) and not app.config.get("TESTING"):
        app.logger.warning(
            "IDENTITY_PROVIDER=sample: identitas berasal dari data contoh, bukan data resmi kampus."
        )

    return app
```

- [ ] **Step 5: Tambahkan dependensi dan kunci `.env`**

Di `requirements.txt`, tambahkan satu baris pada akhir berkas:

```
requests>=2.31,<3.0
```

Di `.env.example`, tambahkan setelah blok `FACE_*`:

```
# Sumber identitas mahasiswa/dosen: sample (data contoh) atau pustik.
IDENTITY_PROVIDER=sample
PUSTIK_BASE_URL=
PUSTIK_API_KEY=
PUSTIK_TIMEOUT=8

# Jumlah maksimal pemeriksaan identitas per menit per alamat IP. 0 mematikan pembatas.
IDENTITY_CHECK_RATE_LIMIT=10
```

Tambahkan blok yang sama ke `.env` dengan nilai yang sama.

- [ ] **Step 6: Pasang dependensi baru**

Run: `uv pip install --python .venv/bin/python -r requirements.txt`
Expected: `requests` terpasang tanpa mengganti versi Flask/SQLAlchemy yang sudah ada.

- [ ] **Step 7: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_identity_provider.py -v`
Expected: PASS, seluruh pengujian lulus.

- [ ] **Step 8: Jalankan seluruh pengujian**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: seluruh pengujian lulus, tanpa kegagalan.

- [ ] **Step 9: Commit**

```bash
git add app/__init__.py app/integrations/__init__.py requirements.txt .env.example tests/test_identity_provider.py
git commit -m "feat: tambahkan pabrik provider identitas dan kunci konfigurasi" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

Catatan: `.env` tidak ikut di-commit karena sudah masuk `.gitignore`.

---

## Task 4: Pembatas laju pemeriksaan identitas

**Files:**
- Modify: `app/utils.py` (tambahkan di akhir berkas)
- Test: `tests/test_rate_limit.py` (baru)

**Interfaces:**
- Consumes: tidak ada.
- Produces: `check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool` (True berarti diizinkan, dan hitungannya bertambah) dan `reset_rate_limit() -> None`.

- [ ] **Step 1: Tulis pengujian yang gagal**

Buat `tests/test_rate_limit.py`:

```python
import pytest

from app.utils import check_rate_limit, reset_rate_limit


@pytest.fixture(autouse=True)
def clean_state():
    reset_rate_limit()
    yield
    reset_rate_limit()


def test_allows_requests_up_to_the_limit():
    for _ in range(3):
        assert check_rate_limit("1.2.3.4", limit=3) is True


def test_blocks_the_request_after_the_limit():
    for _ in range(3):
        check_rate_limit("1.2.3.4", limit=3)

    assert check_rate_limit("1.2.3.4", limit=3) is False


def test_zero_limit_disables_the_limiter():
    for _ in range(50):
        assert check_rate_limit("1.2.3.4", limit=0) is True


def test_keys_are_counted_independently():
    for _ in range(3):
        check_rate_limit("1.2.3.4", limit=3)

    assert check_rate_limit("1.2.3.4", limit=3) is False
    assert check_rate_limit("5.6.7.8", limit=3) is True


def test_reset_clears_the_counter():
    for _ in range(3):
        check_rate_limit("1.2.3.4", limit=3)
    assert check_rate_limit("1.2.3.4", limit=3) is False

    reset_rate_limit()

    assert check_rate_limit("1.2.3.4", limit=3) is True


def test_expired_window_stops_blocking():
    """Jendela nol detik membuat seluruh hitungan lama dianggap kedaluwarsa."""
    for _ in range(3):
        check_rate_limit("1.2.3.4", limit=3, window_seconds=0)

    # Dengan jendela 60 detik, catatan lama masih berlaku dan permintaan diblokir.
    assert check_rate_limit("1.2.3.4", limit=3, window_seconds=60) is False
    # Dengan jendela nol detik, catatan lama sudah dianggap kedaluwarsa.
    assert check_rate_limit("1.2.3.4", limit=3, window_seconds=0) is True
```

- [ ] **Step 2: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_rate_limit' from 'app.utils'`

- [ ] **Step 3: Tulis implementasi**

Tambahkan `import threading` dan `import time` pada blok impor di bagian atas `app/utils.py`, sejajar dengan impor yang sudah ada. Jangan menaruh impor di tengah atau akhir berkas.

Lalu tambahkan di akhir `app/utils.py`:

```python
_rate_limit_lock = threading.Lock()
_rate_limit_hits = {}


def check_rate_limit(key, limit, window_seconds=60):
    """True bila permintaan masih diizinkan; sekaligus menambah satu hitungan."""
    if limit <= 0:
        return True

    now = time.monotonic()
    cutoff = now - window_seconds
    with _rate_limit_lock:
        hits = [stamp for stamp in _rate_limit_hits.get(key, []) if stamp > cutoff]
        if len(hits) >= limit:
            _rate_limit_hits[key] = hits
            return False
        hits.append(now)
        _rate_limit_hits[key] = hits
        return True


def reset_rate_limit():
    """Kosongkan seluruh hitungan. Dipakai fixture pengujian antar-tes."""
    with _rate_limit_lock:
        _rate_limit_hits.clear()
```

- [ ] **Step 4: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_rate_limit.py -v`
Expected: PASS, 6 pengujian lulus.

- [ ] **Step 5: Commit**

```bash
git add app/utils.py tests/test_rate_limit.py
git commit -m "feat: tambahkan pembatas laju untuk pemeriksaan identitas" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

---

## Task 5: Kolom `users` dan migrasi Flask-Migrate

**Files:**
- Modify: `app/models.py:7-40` (tambahkan dua kolom pada `User`)
- Create: `migrations/` (hasil `flask db init`)
- Test: `tests/test_models_identity_columns.py` (baru)

**Interfaces:**
- Consumes: tidak ada.
- Produces: kolom `User.identity_source` dan `User.nidn`.

- [ ] **Step 1: Buat revisi dasar sebelum mengubah model**

Ini urutan yang wajib diikuti. Menjalankan `flask db migrate` setelah menambah kolom akan membuat revisi yang mengira database kosong — revisi itu memuat `create_table` untuk semua tabel dan akan menabrak tabel yang sudah ada saat `upgrade`.

Run:
```bash
.venv/bin/python -m flask --app run.py db init
.venv/bin/python -m flask --app run.py db migrate -m "revisi dasar skema awal"
```

Expected: folder `migrations/` terbentuk, dan satu berkas revisi baru muncul di `migrations/versions/`.

- [ ] **Step 2: Tandai database dev sebagai sudah berada di revisi dasar**

Database pengembangan sudah punya tabel dari `db.create_all()`. Tandai tanpa menjalankan DDL:

Run: `.venv/bin/python -m flask --app run.py db stamp head`
Expected: `Running stamp_revision ... ` tanpa perintah `CREATE TABLE`.

Verifikasi tabel masih utuh:

Run: `.venv/bin/python -m flask --app run.py check-schema`
Expected: `OK: tabel dan kolom database sesuai dengan model aplikasi saat ini.`

- [ ] **Step 3: Tulis pengujian yang gagal**

Buat `tests/test_models_identity_columns.py`:

```python
from app import create_app
from app.extensions import db
from app.models import User


def _app():
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
    })


def test_user_table_has_identity_columns():
    app = _app()
    with app.app_context():
        db.create_all()
        columns = {column.name for column in User.__table__.columns}

    assert "identity_source" in columns
    assert "nidn" in columns


def test_identity_columns_default_to_null():
    app = _app()
    with app.app_context():
        db.create_all()
        user = User(full_name="Uji", email="uji@test.local", role="student")
        user.set_password("password-uji-123")
        db.session.add(user)
        db.session.commit()

        assert user.identity_source is None
        assert user.nidn is None
```

- [ ] **Step 4: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_models_identity_columns.py -v`
Expected: FAIL — `assert 'identity_source' in columns`

- [ ] **Step 5: Tambahkan kolom pada model**

Di `app/models.py`, pada kelas `User`, tambahkan setelah baris `cohort = db.Column(...)`:

```python
    # Asal identitas: PUSTIK_API, SAMPLE, atau MANUAL. NULL berarti diisi manual.
    identity_source = db.Column(db.String(20), nullable=True)
    # Nomor Induk Dosen Nasional, terpisah dari employee_id yang menyimpan NIK.
    nidn = db.Column(db.String(30), nullable=True)
```

- [ ] **Step 6: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_models_identity_columns.py -v`
Expected: PASS, 2 pengujian lulus.

- [ ] **Step 7: Buat revisi untuk dua kolom baru**

Run: `.venv/bin/python -m flask --app run.py db migrate -m "tambah identity_source dan nidn pada users"`

Expected: satu berkas revisi baru. Buka berkas itu dan pastikan isinya hanya berisi dua `op.add_column` untuk `users` — `identity_source` dan `nidn` — tanpa `create_table`, tanpa `drop_table`, dan tanpa `drop_column`. Bila isinya berbeda, jangan lanjutkan; periksa ulang langkah 2.

- [ ] **Step 8: Terapkan revisi**

Run: `.venv/bin/python -m flask --app run.py db upgrade`
Expected: `Running upgrade  -> ..., tambah identity_source dan nidn pada users`, tanpa galat.

- [ ] **Step 9: Pastikan data dev selamat**

Run:
```bash
.venv/bin/python -m flask --app run.py check-schema
.venv/bin/python -c "from app import create_app; from app.models import User, StudyProgram; app=create_app(); ctx=app.app_context(); ctx.push(); print('users:', User.query.count()); print('prodi:', StudyProgram.query.count())"
```

Expected: `check-schema` mencetak OK, dan jumlah `users` tetap 1 serta `prodi` tetap 15.

- [ ] **Step 10: Jalankan seluruh pengujian**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: seluruh pengujian lulus.

- [ ] **Step 11: Commit**

```bash
git add app/models.py migrations/ tests/test_models_identity_columns.py
git commit -m "feat: tambahkan kolom identity_source dan nidn beserta migrasinya" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

---

## Task 6: Route pemeriksaan identitas dan partial kartu

**Files:**
- Modify: `app/blueprints/auth.py`
- Create: `app/templates/auth/_identity_card.html`
- Create: `app/templates/auth/_identity_error.html`
- Test: `tests/test_register_flow.py` (baru)

**Interfaces:**
- Consumes: `get_identity_provider()`, `identity_provider_is_sample()` (Task 3), `check_rate_limit()` (Task 4), kolom `User.identity_source` dan `User.nidn` (Task 5), seluruh kelas galat dan `status_label`/`status_tone` (Task 1).
- Produces:
  - `POST /register/check` → potongan HTML, `text/html`.
  - Helper internal `_valid_identifier(value) -> bool`, `_match_program(identity) -> StudyProgram | None`, `_eligibility(identity) -> tuple[StudyProgram | None, str | None]`, `_resolve_identity(jenis, identifier) -> Identity`.
  - Partial `auth/_identity_card.html` menerima `identity`, `status_label`, `status_tone`, `blocked_reason`, `already_registered`.
  - Partial `auth/_identity_error.html` menerima `message`.

- [ ] **Step 1: Tulis pengujian yang gagal**

Buat `tests/test_register_flow.py`:

```python
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
```

- [ ] **Step 2: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_register_flow.py -v`
Expected: FAIL — seluruh pengujian menerima status 404 karena route belum ada.

- [ ] **Step 3: Tulis partial kartu dan galat**

Buat `app/templates/auth/_identity_error.html`:

```html
<div class="alert alert-danger identity-error" role="alert">
  <i class="bi bi-exclamation-circle"></i> {{ message }}
</div>
```

Buat `app/templates/auth/_identity_card.html`:

```html
<div class="identity-card" data-identity-state="{% if already_registered %}already{% elif blocked_reason %}blocked{% else %}ok{% endif %}">
  <div class="identity-card-head">
    <span class="identity-card-icon"><i class="bi bi-person-badge"></i></span>
    <div class="identity-card-copy">
      <strong>{{ identity.name }}</strong>
      <small>{{ 'Mahasiswa' if identity.kind == 'student' else 'Dosen' }} · {{ identity.identifier }}</small>
    </div>
    <span class="status-pill {{ status_tone }}">{{ status_label }}</span>
  </div>
  <div class="detail-list">
    <div class="detail-item"><small>Program studi</small><strong>{{ identity.program_name or '—' }}</strong></div>
    <div class="detail-item"><small>Fakultas</small><strong>{{ identity.faculty or '—' }}</strong></div>
    <div class="detail-item"><small>Semester</small><strong>{{ identity.semester if identity.semester else '—' }}</strong></div>
    <div class="detail-item"><small>Angkatan</small><strong>{{ identity.cohort or '—' }}</strong></div>
    {% if identity.nidn %}
    <div class="detail-item"><small>NIDN</small><strong>{{ identity.nidn }}</strong></div>
    {% endif %}
    {% if identity.kind == 'lecturer' %}
    <div class="detail-item"><small>Jabatan struktural</small><strong>{{ identity.positions|join(', ') or 'Tidak ada jabatan struktural' }}</strong></div>
    {% endif %}
  </div>
  {% if already_registered %}
  <div class="callout warning"><i class="bi bi-info-circle"></i><span>Akun dengan nomor ini sudah terdaftar. Silakan <a href="{{ url_for('auth.login') }}">masuk</a>.</span></div>
  {% elif blocked_reason %}
  <div class="callout warning"><i class="bi bi-shield-exclamation"></i><span>{{ blocked_reason }}</span></div>
  {% endif %}
</div>
```

- [ ] **Step 4: Tulis route pemeriksaan**

Di `app/blueprints/auth.py`, ubah blok impor di bagian atas menjadi:

```python
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func
from ..extensions import db
from ..integrations import get_identity_provider
from ..integrations.base import IdentityError, IdentityNotActive, ProgramNotRegistered, status_label, status_tone
from ..models import User, StudyProgram
from ..utils import check_rate_limit, dashboard_endpoint, log_action
```

Tambahkan helper berikut setelah `_safe_next_url`:

```python
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
```

Tambahkan route setelah `register`:

```python
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

    provider = get_identity_provider()
    try:
        identity = provider.resolve_lecturer(identifier) if jenis == "dosen" else provider.resolve_student(identifier)
    except IdentityError as exc:
        current_app.logger.warning("Pemeriksaan identitas gagal: %s", exc.detail or exc)
        return render_template("auth/_identity_error.html", message=exc.user_message), _status_code_for(exc)

    program, blocked_reason = _eligibility(identity)
    existing = User.query.filter_by(**{field: identifier}).first()

    return render_template(
        "auth/_identity_card.html",
        identity=identity,
        status_label=status_label(identity.academic_status),
        status_tone=status_tone(identity.academic_status),
        blocked_reason=blocked_reason,
        already_registered=existing is not None,
    )
```

- [ ] **Step 5: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_register_flow.py -v`
Expected: PASS, 10 pengujian lulus.

- [ ] **Step 6: Commit**

```bash
git add app/blueprints/auth.py app/templates/auth/_identity_card.html app/templates/auth/_identity_error.html tests/test_register_flow.py
git commit -m "feat: tambahkan route pemeriksaan identitas dan partial kartu konfirmasi" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

---

## Task 7: Route pembuatan akun mahasiswa dan dosen

**Files:**
- Modify: `app/blueprints/auth.py`
- Test: `tests/test_register_flow.py` (tambahan)

**Interfaces:**
- Consumes: `_valid_identifier`, `_normalize_identifier`, `_eligibility`, `_status_code_for` (Task 6).
- Produces: `POST /register/student` dan `POST /register/lecturer`.

- [ ] **Step 1: Tulis pengujian yang gagal**

Tambahkan ke `tests/test_register_flow.py`:

```python
def _register(client, path, **fields):
    return client.post(path, data=fields)


def test_student_registration_uses_provider_identity(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="ayu@test.local", password="rahasia-123", password_confirm="rahasia-123",
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
        email="palsu@test.local", password="rahasia-123", password_confirm="rahasia-123",
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
        email="dwi@test.local", password="rahasia-123", password_confirm="rahasia-123",
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
        email="ganda@test.local", password="rahasia-123", password_confirm="rahasia-123",
    )

    with app.app_context():
        assert User.query.filter_by(email="ganda@test.local").count() == 1
        assert User.query.filter_by(employee_id="0012345678").count() == 0


def test_inactive_status_is_rejected_at_creation(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312002",
        email="lulus@test.local", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 422
    with app.app_context():
        assert User.query.filter_by(email="lulus@test.local").count() == 0


def test_unregistered_program_is_rejected_at_creation(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312003",
        email="robot@test.local", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 422
    with app.app_context():
        assert User.query.filter_by(email="robot@test.local").count() == 0


def test_duplicate_email_is_rejected_without_touching_existing_account(app, client):
    with app.app_context():
        existing = User(full_name="Pemilik Lama", email="ayu@test.local", npm="20999999",
                        role="student", active=True)
        existing.set_password("password-uji-123")
        db.session.add(existing)
        db.session.commit()

    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="ayu@test.local", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 400
    with app.app_context():
        assert User.query.filter_by(email="ayu@test.local").count() == 1
        assert User.query.filter_by(email="ayu@test.local").one().full_name == "Pemilik Lama"
        assert User.query.filter_by(npm="23312001").count() == 0


def test_duplicate_identifier_is_rejected(app, client):
    with app.app_context():
        existing = User(full_name="Sudah Ada", email="lama@test.local", npm="23312001",
                        role="student", active=True)
        existing.set_password("password-uji-123")
        db.session.add(existing)
        db.session.commit()

    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="baru@test.local", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 400
    with app.app_context():
        assert User.query.filter_by(email="baru@test.local").count() == 0


def test_password_mismatch_is_rejected(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="ayu@test.local", password="rahasia-123", password_confirm="beda-123",
    )

    assert response.status_code == 400
    with app.app_context():
        assert User.query.filter_by(email="ayu@test.local").count() == 0


def test_short_password_is_rejected(app, client):
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="23312001",
        email="ayu@test.local", password="pendek", password_confirm="pendek",
    )

    assert response.status_code == 400


def test_unknown_identifier_is_rejected_at_creation(app, client):
    """Pemeriksaan ulang saat pembuatan akun tetap wajib, walau form dikirim langsung."""
    response = _register(
        client, "/register/student",
        jenis="mahasiswa", npm="00000000",
        email="hantu@test.local", password="rahasia-123", password_confirm="rahasia-123",
    )

    assert response.status_code == 404
    with app.app_context():
        assert User.query.filter_by(email="hantu@test.local").count() == 0
```

- [ ] **Step 2: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_register_flow.py -v -k "registration or rejected or ignored"`
Expected: FAIL — status 404 karena route belum ada.

- [ ] **Step 3: Tulis implementasi**

Di blok impor `app/blueprints/auth.py` (dari Task 6), tambahkan:

```python
from ..integrations import identity_provider_is_sample
from email_validator import EmailNotValidError, validate_email
```

Lalu tambahkan di `app/blueprints/auth.py`, setelah `register_check`:

```python
def _register_account(jenis, identifier, email, password, password_confirm):
    """Bangun akun dari hasil provider.

    Mengembalikan (user, failure, identity):
    - berhasil: (user, None, identity)
    - gagal:    (None, (pesan, kode), identity_atau_None)

    Identity tetap dikembalikan meski gagal supaya halaman yang dirender ulang
    masih menampilkan kartu konfirmasi. Tanpa itu, pengguna kehilangan konteks
    identitasnya hanya karena salah mengetik kata sandi.
    """
    field = "nik" if jenis == "dosen" else "npm"
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
```

Tambahkan helper `_active_programs`:

```python
def _active_programs():
    return StudyProgram.query.filter_by(is_active=True).order_by(StudyProgram.name).all()
```

Lalu sesuaikan route `register()` yang sudah ada:

1. Hapus baris
   `programs = StudyProgram.query.filter_by(is_active=True).order_by(StudyProgram.name).all()`.
   Program studi kini diambil di dalam `_render_register()`, sehingga variabel `programs` di
   fungsi ini menjadi tidak terpakai dan harus dibuang, bukan dibiarkan menggantung.
2. Ganti baris terakhir
   `return render_template("auth/register.html", page_title="Daftar Akun", programs=programs)`
   menjadi:

```python
    return _render_register(
        jenis="dosen" if (request.args.get("jenis") or "").strip().lower() == "dosen" else "mahasiswa"
    )
```

- [ ] **Step 4: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_register_flow.py -v`
Expected: PASS, seluruh pengujian lulus.

- [ ] **Step 5: Commit**

```bash
git add app/blueprints/auth.py tests/test_register_flow.py
git commit -m "feat: tambahkan pendaftaran akun mahasiswa dan dosen dari identitas provider" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

---

## Task 8: Halaman register dua panel dan CSS

**Files:**
- Modify: `app/templates/auth/register.html` (tulis ulang)
- Modify: `app/static/css/app.css` (tambahkan di akhir berkas)
- Test: `tests/test_register_page.py` (baru)

**Interfaces:**
- Consumes: partial `auth/_identity_card.html` dan `auth/_identity_error.html` (Task 6); konteks `jenis` dan `sample_mode` dari `register()` (Task 7).
- Produces: DOM yang dibutuhkan Task 9 — `[data-register-page]` dengan atribut `data-check-url`, `[data-tab]` berisi `data-jenis`, `[data-pane]` berisi `data-jenis`, `[data-check-form]`, `[data-identity-slot]`, `[data-account-form]`.

- [ ] **Step 1: Tulis pengujian yang gagal**

Buat `tests/test_register_page.py`:

```python
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
```

- [ ] **Step 2: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_register_page.py -v`
Expected: FAIL — `assert 'name="nik"' in body`

- [ ] **Step 3: Tulis ulang halaman register**

Ganti seluruh isi `app/templates/auth/register.html`:

```html
{% extends 'base.html' %}
{% block auth_content %}
{% macro account_fields(prefix, jenis, label) %}
      <label for="{{ prefix }}-email">Email aktif</label>
      <div class="input-icon-wrap"><i class="bi bi-envelope"></i><input id="{{ prefix }}-email" name="email" type="email" placeholder="nama@email.com" value="{{ request.form.get('email','') }}" required></div>
      <label for="{{ prefix }}-password">Password <span class="optional-text">(minimal 8 karakter)</span></label>
      <div class="input-icon-wrap"><i class="bi bi-lock"></i><input id="{{ prefix }}-password" name="password" type="password" autocomplete="new-password" placeholder="Buat password yang kuat" required><button type="button" class="toggle-password" data-target="{{ prefix }}-password" aria-label="Tampilkan password"><i class="bi bi-eye"></i></button></div>
      <label for="{{ prefix }}-password-confirm">Konfirmasi password</label>
      <div class="input-icon-wrap"><i class="bi bi-lock-fill"></i><input id="{{ prefix }}-password-confirm" name="password_confirm" type="password" autocomplete="new-password" placeholder="Ulangi password" required></div>
{% endmacro %}
<div class="auth-page register-page" data-register-page data-check-url="{{ url_for('auth.register_check') }}">
  <section class="auth-hero register-hero" style="--campus-image: url('{{ url_for('static', filename='images/foto-kampus.jpg') }}')">
    <div class="auth-brand"><img class="auth-logo" src="{{ url_for('static', filename='images/logo-teknokrat.png') }}" alt="Logo Universitas Teknokrat Indonesia"><div><strong>UNIVERSITAS TEKNOKRAT INDONESIA</strong><small>SMART ATTENDANCE PORTAL</small></div></div>
    <div class="auth-hero-copy"><span class="hero-kicker">MULAI DARI SINI</span><h1>Verifikasi identitas,<br><em>lalu buat akunmu.</em></h1><p>Akun mahasiswa dan dosen dibuat dari data akademik resmi, sehingga nama, program studi, dan angkatan tidak perlu diketik ulang.</p><div class="register-steps"><div class="step-item active"><span>01</span><div><strong>Verifikasi identitas</strong><small>Masukkan NPM atau NIK</small></div></div><div class="step-item"><span>02</span><div><strong>Buat akun</strong><small>Email dan kata sandi</small></div></div><div class="step-item"><span>03</span><div><strong>Daftarkan wajah</strong><small>Dilakukan setelah login</small></div></div><div class="step-item"><span>04</span><div><strong>Pilih mata kuliah</strong><small>Kelas pada semester aktif</small></div></div></div></div>
    <div class="auth-hero-footer"><span class="red-line"></span><span>Data yang benar membantu menjaga akurasi presensi.</span></div><div class="hero-decoration hero-decoration-one"></div><div class="hero-decoration hero-decoration-two"></div>
  </section>
  <section class="auth-panel"><div class="auth-form-wrap register-form-wrap"><span class="form-kicker">REGISTRASI AKUN</span><h2>Daftar akun</h2>
    {% if sample_mode %}<div class="identity-badge-sample"><i class="bi bi-exclamation-triangle"></i><span>Mode data contoh — identitas berasal dari data uji, bukan data resmi kampus.</span></div>{% endif %}
    <p class="muted-intro">Masukkan NPM atau NIK agar data Anda dicocokkan dengan data akademik resmi universitas.</p>

    <div class="identity-tabs" role="tablist" aria-label="Jenis akun">
      <a class="identity-tab {% if jenis != 'dosen' %}active{% endif %}" role="tab" data-tab data-jenis="mahasiswa" aria-selected="{{ 'true' if jenis != 'dosen' else 'false' }}" href="{{ url_for('auth.register') }}?jenis=mahasiswa">Mahasiswa</a>
      <a class="identity-tab {% if jenis == 'dosen' %}active{% endif %}" role="tab" data-tab data-jenis="dosen" aria-selected="{{ 'true' if jenis == 'dosen' else 'false' }}" href="{{ url_for('auth.register') }}?jenis=dosen">Dosen</a>
    </div>

    <div class="identity-pane" data-pane="mahasiswa" data-jenis="mahasiswa" {% if jenis == 'dosen' %}hidden{% endif %}>
      <form method="post" action="{{ url_for('auth.register_check') }}" class="auth-form identity-check-form" data-check-form>
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="jenis" value="mahasiswa">
        <label for="npm">Nomor Pokok Mahasiswa (NPM)</label>
        <div class="identity-check-row">
          <div class="input-icon-wrap"><i class="bi bi-card-text"></i><input id="npm" name="npm" type="text" inputmode="numeric" placeholder="Masukkan NPM" required></div>
          <button class="btn btn-outline-primary identity-check-button" type="submit" data-check-button disabled>Cek</button>
        </div>
      </form>
      <div data-identity-slot>{% if identity and jenis != 'dosen' %}{% include 'auth/_identity_card.html' %}{% endif %}</div>
      <form method="post" action="{{ url_for('auth.register_student') }}" class="auth-form" data-account-form {% if not identity or blocked_reason or already_registered %}hidden{% endif %}>
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="jenis" value="mahasiswa">
        <input type="hidden" name="npm" value="{{ request.form.get('npm', '') }}">
        {{ account_fields('mhs', 'mahasiswa', 'NPM') }}
        <div class="form-note"><i class="bi bi-info-circle"></i><span>Pendaftaran wajah dilakukan setelah Anda masuk ke dashboard.</span></div>
        <button class="btn btn-primary btn-lg w-100 auth-submit" type="submit">Buat akun <i class="bi bi-arrow-right"></i></button>
      </form>
    </div>

    <div class="identity-pane" data-pane="dosen" data-jenis="dosen" {% if jenis != 'dosen' %}hidden{% endif %}>
      <form method="post" action="{{ url_for('auth.register_check') }}" class="auth-form identity-check-form" data-check-form>
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="jenis" value="dosen">
        <label for="nik">Nomor Induk Kepegawaian (NIK)</label>
        <div class="identity-check-row">
          <div class="input-icon-wrap"><i class="bi bi-person-badge"></i><input id="nik" name="nik" type="text" inputmode="numeric" placeholder="Masukkan NIK" required></div>
          <button class="btn btn-outline-primary identity-check-button" type="submit" data-check-button disabled>Cek</button>
        </div>
      </form>
      <div data-identity-slot>{% if identity and jenis == 'dosen' %}{% include 'auth/_identity_card.html' %}{% endif %}</div>
      <form method="post" action="{{ url_for('auth.register_lecturer') }}" class="auth-form" data-account-form {% if not identity or blocked_reason or already_registered %}hidden{% endif %}>
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="jenis" value="dosen">
        <input type="hidden" name="nik" value="{{ request.form.get('nik', '') }}">
        {{ account_fields('dsn', 'dosen', 'NIK') }}
        <div class="form-note"><i class="bi bi-info-circle"></i><span>Kelas yang Anda ampu diatur setelah login.</span></div>
        <button class="btn btn-primary btn-lg w-100 auth-submit" type="submit">Buat akun <i class="bi bi-arrow-right"></i></button>
      </form>
    </div>

    <p class="auth-switch">Sudah mempunyai akun? <a href="{{ url_for('auth.login') }}">Masuk di sini</a></p>
  </div><div class="auth-panel-footer">© {{ current_year }} Universitas Teknokrat Indonesia</div></section>
</div>
{% endblock %}
```

- [ ] **Step 4: Tambahkan CSS**

Tambahkan di akhir `app/static/css/app.css`:

```css
/* --- Verifikasi identitas pada halaman register --- */
.identity-badge-sample{display:flex;align-items:flex-start;gap:9px;background:#fff7e9;border:1px solid #f6e7ca;color:#8d6828;border-radius:10px;padding:11px 12px;font-size:10px;line-height:1.6;margin-bottom:16px}
.identity-badge-sample i{font-size:15px;flex-shrink:0;margin-top:1px}
.identity-tabs{display:flex;gap:4px;background:#f1f4f9;border:1px solid #e6ecf5;border-radius:100px;padding:4px;margin-bottom:20px}
.identity-tab{flex:1;text-align:center;padding:9px 12px;border-radius:100px;font-size:11px;font-weight:750;color:#697386;transition:all .15s ease}
.identity-tab:hover{color:#172033}
.identity-tab.active{background:#fff;color:var(--blue);box-shadow:0 2px 8px rgba(20,48,86,.08)}
.identity-check-row{display:flex;gap:9px;align-items:stretch;margin-bottom:14px}
.identity-check-row .input-icon-wrap{flex:1}
.identity-check-button{border-radius:100px;padding:0 22px;height:45px;font-weight:750;white-space:nowrap}
.identity-check-button:disabled{opacity:.5}
.identity-card{border:1px solid #e2e9f3;background:#f9fbfe;border-radius:13px;padding:15px;margin-bottom:16px}
.identity-card-head{display:flex;align-items:center;gap:11px;margin-bottom:13px}
.identity-card-icon{width:40px;height:40px;border-radius:12px;background:#eaf2ff;color:#2b66bc;display:grid;place-items:center;font-size:18px;flex-shrink:0}
.identity-card-copy{display:flex;flex-direction:column;gap:3px;min-width:0;flex:1}
.identity-card-copy strong{font-size:12px;color:#22385a}
.identity-card-copy small{font-size:10px;color:#8593a7}
.identity-card .detail-list{margin-bottom:0}
.identity-card .callout{margin-top:12px}
.identity-error{display:flex;align-items:center;gap:8px;margin-bottom:14px}
.identity-pane[hidden]{display:none}
@media(max-width:600px){.identity-check-row{flex-direction:column}.identity-check-button{width:100%}.identity-tab{font-size:10px;padding:8px 6px}}
```

- [ ] **Step 5: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_register_page.py -v`
Expected: PASS, 7 pengujian lulus.

- [ ] **Step 6: Jalankan pengujian lama**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: seluruh pengujian lulus, termasuk `tests/test_web_smoke.py::test_auth_pages_load`.

- [ ] **Step 7: Commit**

```bash
git add app/templates/auth/register.html app/static/css/app.css tests/test_register_page.py
git commit -m "feat: tulis ulang halaman register dengan dua panel dan verifikasi identitas" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

---

## Task 9: Skrip halaman register

**Files:**
- Create: `app/static/js/register.js`
- Modify: `app/templates/auth/register.html` (tambahkan blok `scripts`)
- Modify: `tests/test_register_page.py` (tambahan)

**Interfaces:**
- Consumes: DOM dan kontrak `data-*` dari Task 8; `POST /register/check` dari Task 6.
- Produces: perilaku pindah tab tanpa muat ulang, tombol Cek aktif/nonaktif, penyuntikan potongan HTML ke `[data-identity-slot]`, dan pembukaan `[data-account-form]`.

Catatan kejujuran: interaksi JavaScript tidak tercakup pengujian otomatis. Proyek ini belum punya perkakas uji browser. Pengujian di task ini hanya memeriksa kontrak DOM dan keberadaan skrip; perilakunya diverifikasi manual pada Step 6.

- [ ] **Step 1: Tulis pengujian yang gagal**

Tambahkan ke `tests/test_register_page.py`:

```python
def test_page_loads_register_script(client):
    body = client.get("/register").get_data(as_text=True)

    assert "js/register.js" in body


def test_register_script_file_exists():
    from pathlib import Path

    assert Path("app/static/js/register.js").is_file()
```

- [ ] **Step 2: Jalankan pengujian, pastikan gagal**

Run: `.venv/bin/python -m pytest tests/test_register_page.py -v -k script`
Expected: FAIL — `assert 'js/register.js' in body`

- [ ] **Step 3: Tulis skrip**

Buat `app/static/js/register.js`:

```javascript
(() => {
  const page = document.querySelector('[data-register-page]');
  if (!page) return;

  const checkUrl = page.dataset.checkUrl;
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  function paneFor(jenis) {
    return page.querySelector(`[data-pane="${jenis}"]`);
  }

  function activateTab(jenis) {
    page.querySelectorAll('[data-tab]').forEach((tab) => {
      const active = tab.dataset.jenis === jenis;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    page.querySelectorAll('[data-pane]').forEach((pane) => {
      pane.hidden = pane.dataset.jenis !== jenis;
    });
  }

  page.querySelectorAll('[data-tab]').forEach((tab) => {
    tab.addEventListener('click', (event) => {
      event.preventDefault();
      const jenis = tab.dataset.jenis;
      activateTab(jenis);
      history.replaceState(null, '', `${window.location.pathname}?jenis=${jenis}`);
    });
  });

  page.querySelectorAll('[data-pane]').forEach((pane) => {
    const form = pane.querySelector('[data-check-form]');
    const slot = pane.querySelector('[data-identity-slot]');
    const accountForm = pane.querySelector('[data-account-form]');
    const button = pane.querySelector('[data-check-button]');
    const input = form.querySelector('input:not([type="hidden"])');

    input.addEventListener('input', () => {
      button.disabled = input.value.trim().length === 0;
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      button.disabled = true;
      const originalLabel = button.textContent;
      button.textContent = 'Memeriksa...';
      slot.innerHTML = '';
      accountForm.hidden = true;

      try {
        const response = await fetch(checkUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          },
          body: new URLSearchParams(new FormData(form)),
        });
        const html = await response.text();
        slot.innerHTML = html;

        const identifierField = accountForm.querySelector('input[type="hidden"][name="npm"], input[type="hidden"][name="nik"]');
        if (identifierField) identifierField.value = input.value.trim();

        const state = slot.querySelector('[data-identity-state]')?.dataset.identityState;
        if (response.ok && state === 'ok') {
          accountForm.hidden = false;
          const email = accountForm.querySelector('input[name="email"]');
          if (email) email.focus();
        }
      } catch (error) {
        slot.innerHTML = '<div class="alert alert-danger identity-error">Periksa koneksi internet Anda lalu coba lagi.</div>';
      } finally {
        button.textContent = originalLabel;
        button.disabled = input.value.trim().length === 0;
      }
    });
  });
})();
```

- [ ] **Step 4: Muat skrip pada halaman**

Di `app/templates/auth/register.html`, tambahkan sebelum `{% endblock %}` terakhir:

```html
{% block scripts %}<script src="{{ url_for('static', filename='js/register.js') }}"></script>{% endblock %}
```

- [ ] **Step 5: Jalankan pengujian, pastikan lulus**

Run: `.venv/bin/python -m pytest tests/test_register_page.py -v`
Expected: PASS, 9 pengujian lulus.

- [ ] **Step 6: Verifikasi manual di browser**

Jalankan server: `.venv/bin/python run.py`, buka `http://127.0.0.1:5000/register`.

Periksa berurutan:
1. Tombol Cek nonaktif saat kolom kosong, aktif setelah diisi.
2. Isi `23312001` lalu klik Cek — kartu identitas muncul tanpa muat ulang halaman.
3. Form email dan kata sandi terbuka otomatis.
4. Isi `23312002` — kartu muncul dengan lencana "Lulus" dan pesan blokir, form tetap tertutup.
5. Isi `99999999` — muncul pesan gangguan sistem.
6. Isi `abc` — muncul pesan tidak valid.
7. Klik tab Dosen — panel berganti tanpa muat ulang, alamat berubah menjadi `?jenis=dosen`.
8. Matikan JavaScript di browser, muat ulang, dan pastikan tab Dosen masih dapat dibuka lewat tautannya.

Hentikan server setelah selesai (`Ctrl+C`) dan pastikan port 5000 bebas.

- [ ] **Step 7: Commit**

```bash
git add app/static/js/register.js app/templates/auth/register.html tests/test_register_page.py
git commit -m "feat: tambahkan skrip tab dan pemeriksaan identitas pada halaman register" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```

---

## Task 10: Dokumentasi dan verifikasi menyeluruh

**Files:**
- Modify: `README.md`
- Modify: `docs/INTEGRASI_PUSTIK.md` (tambahkan tautan ke spec dan rencana)

**Interfaces:**
- Consumes: seluruh task sebelumnya.
- Produces: tidak ada kode baru.

- [ ] **Step 1: Tambahkan bagian provider identitas pada README**

Sisipkan setelah bagian "Alur data akademik" di `README.md`:

```markdown
## Verifikasi identitas mahasiswa dan dosen

Pendaftaran akun memverifikasi NPM (mahasiswa) atau NIK (dosen) ke sumber identitas sebelum
akun dibuat. Nama, program studi, dan angkatan diambil dari sumber itu — tidak diketik oleh
pendaftar, dan nilai yang dikirim lewat form tidak dipercaya.

Sumber identitas diatur lewat `.env`:

```env
IDENTITY_PROVIDER=sample        # sample (data contoh) atau pustik (data resmi kampus)
PUSTIK_BASE_URL=
PUSTIK_API_KEY=
PUSTIK_TIMEOUT=8
IDENTITY_CHECK_RATE_LIMIT=10
```

Dengan `IDENTITY_PROVIDER=sample`, halaman register menampilkan lencana **"Mode data contoh"**
dan server menulis peringatan di log. Data contoh hanya untuk pengembangan; jangan dipakai
untuk data mahasiswa sungguhan.

Akun data contoh yang dapat dipakai menguji:

| Identifier | Jenis | Keadaan |
| --- | --- | --- |
| `23312001` | NPM | Informatika, semester 5, angkatan 2023, aktif |
| `23312002` | NPM | Informatika, status Lulus — pendaftaran ditolak |
| `23312003` | NPM | Program studi tidak terdaftar — pendaftaran ditolak |
| `0012345678` | NIK | Dosen Informatika, aktif |
| `99999999` | keduanya | Menyimulasikan gangguan pada sumber identitas |

Provider `pustik` belum boleh diarahkan ke server PUSTIK sungguhan sampai kontrak resminya
dikonfirmasi. Pemetaan responsnya masih berdasarkan dugaan; lihat
`docs/SPEC_REGISTER_PUSTIK.md` bagian 4.5.

### Perubahan skema setelah migrasi diaktifkan

Database tidak lagi disiapkan dengan `init-db` untuk perubahan lanjutan. Setelah mengubah model:

```bash
python -m flask --app run.py db migrate -m "keterangan perubahan"
python -m flask --app run.py db upgrade
python -m flask --app run.py check-schema
```

`init-db` tetap tersedia untuk database kosong.
```

- [ ] **Step 2: Tambahkan tautan silang pada dokumen temuan**

Di akhir `docs/INTEGRASI_PUSTIK.md`, tambahkan:

```markdown
## Lanjutan

Rencana teknis dan status implementasi integrasi ini ada di
`docs/SPEC_REGISTER_PUSTIK.md`.
```

- [ ] **Step 3: Jalankan seluruh pengujian**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: seluruh pengujian lulus tanpa kegagalan.

- [ ] **Step 4: Periksa kesesuaian skema database dev**

Run: `.venv/bin/python -m flask --app run.py check-schema`
Expected: `OK: tabel dan kolom database sesuai dengan model aplikasi saat ini.`

- [ ] **Step 5: Periksa daftar route**

Run: `.venv/bin/python -m flask --app run.py routes | grep register`
Expected: muncul `/register`, `/register/check`, `/register/student`, `/register/lecturer`.

- [ ] **Step 6: Jalankan pemeriksaan mutu kode**

Run: `quality_fix` pada berkas yang diubah, lalu `.venv/bin/python -m pytest tests/ -q` sekali lagi.
Expected: tidak ada perubahan yang merusak pengujian.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/INTEGRASI_PUSTIK.md
git commit -m "docs: jelaskan provider identitas, akun data contoh, dan alur migrasi" -m "Co-authored-by: CommandCodeBot <noreply@commandcode.ai>"
```
