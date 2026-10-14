# Foto Bukti Presensi — Rencana Patch 60 Menit Tanpa Radius

Branch: `feature/foto-bukti-60m-tanpa-radius`

## Status repository

This document records the intended behavior only. The implementation ZIP distributed in the ChatGPT conversation has **not yet been committed into this GitHub branch**. Do not treat this documentation commit as an application-code upgrade.

## Intended behavior

- After a student's attendance token/session checks, liveness challenge, and face match succeed, save one compressed evidence image.
- Keep evidence files in private server-side storage, outside `static/`, and serve them only through an authenticated route.
- Permit access for up to 60 minutes from the time the server saves the evidence.
- A scheduled server cleanup physically deletes expired files; attendance history remains.
- Disable GPS/radius enforcement for attendance, as requested.
- Keep evidence photos separate from the long-lived Face Profile.
- Restrict lecturers to evidence for sessions/classes they teach.

## Required verification before deployment

- Verify that the photo is only saved after the complete attendance verification succeeds.
- Verify lecturer authorization on every evidence-photo request.
- Verify access is denied after expiry even if the cleanup job has not run yet.
- Verify cleanup physically deletes files and retries failures.
- Verify attendance rows remain intact when evidence is deleted.
- Verify Windows Task Scheduler or a production scheduler runs cleanup at least once per minute.
- Verify backup/log/cache policy does not retain expired evidence indefinitely.
- Run end-to-end tests against a backup of the local SQLite database before merging.

The source patch must be added separately to this branch before it can be considered a code commit. Do not replace `main` until the implementation has been reviewed and tested.
