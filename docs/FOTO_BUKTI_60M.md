# Foto Bukti Presensi — Retensi 60 Menit (Patch)

Branch: feature/foto-bukti-60m-tanpa-radius

This branch archives the photo-evidence patch for the local Smart Attendance UTI V8 workspace. It is intentionally isolated from `main`.

## Intended behavior
- Store a single compressed JPEG evidence frame only after token/session checks, liveness, and face match succeed.
- Keep evidence files outside `static/` and serve them through an authenticated, lecturer-authorized route.
- Allow evidence access for 60 minutes after the server saves it.
- Clean up expired evidence files periodically; attendance rows remain intact.
- Do not use browser GPS/radius to accept or reject attendance in this patch.
- Keep face enrollment profiles separate from temporary attendance evidence.

## Archive
The source bundle is stored in `patches/smart-attendance-photo-evidence-source.zip.b64.part01` through `part04` as Base64 text. This avoids committing a binary ZIP using the GitHub connector.

From the repository root in PowerShell, reconstruct the ZIP:
```powershell
$parts = @(
  "patches/smart-attendance-photo-evidence-source.zip.b64.part01",
  "patches/smart-attendance-photo-evidence-source.zip.b64.part02",
  "patches/smart-attendance-photo-evidence-source.zip.b64.part03",
  "patches/smart-attendance-photo-evidence-source.zip.b64.part04"
)
$b64 = ($parts | ForEach-Object { Get-Content $_ -Raw }) -join ""
[IO.File]::WriteAllBytes("smart-attendance-photo-evidence-source.zip", [Convert]::FromBase64String($b64))
```

The archive contains only source code and documentation, not `.env`, SQLite database files, student photos, virtual environments, or backups.

## Important
The default branch `main` was not changed. The ZIP is a patch bundle for the locally installed V8 project. Apply it only after a local backup and review its installer/documents before running. Full end-to-end tests against the local SQLite database and browser are not run by the GitHub commit operation.
