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
