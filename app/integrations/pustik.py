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
        if isinstance(raw, dict) and isinstance(raw.get("identity"), dict):
            raw = raw["identity"]
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
