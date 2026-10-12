"""Optional DeepFace / ArcFace adapter and basic MediaPipe liveness checks.

The Flask application can start without optional face dependencies. Face enrollment
and verification fail closed with a clear message until the required packages exist.

Compatibility note:
- The liveness code uses MediaPipe's legacy Solutions FaceMesh API.
- Install mediapipe==0.10.21 in the project's virtual environment for that API.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import os


class FaceEngineError(Exception):
    """Expected error that can be safely shown in the UI."""


def _decode_data_url(data_url: str):
    """Decode a browser camera data URL into an OpenCV BGR image."""
    if not data_url or "," not in data_url:
        raise FaceEngineError("Data gambar kamera tidak valid. Coba ambil gambar kembali.")

    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise FaceEngineError(
            "OpenCV belum terpasang. Ikuti langkah instalasi Face Recognition di README."
        ) from exc

    try:
        encoded = data_url.split(",", 1)[1]
        raw = base64.b64decode(encoded, validate=True)
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Gambar tidak bisa dibaca")
        return image
    except Exception as exc:
        raise FaceEngineError(
            "Gambar kamera tidak bisa dibaca. Coba ulangi dengan pencahayaan yang baik."
        ) from exc


def extract_embedding(data_url: str) -> list[float]:
    """Extract a face embedding using DeepFace's ArcFace model."""
    image = _decode_data_url(data_url)

    try:
        from deepface import DeepFace
    except ImportError as exc:
        raise FaceEngineError(
            "Modul Face Recognition belum terpasang. Aktifkan virtual environment lalu "
            "jalankan: pip install -r requirements-face.txt"
        ) from exc

    model_name = os.getenv("FACE_MODEL", "ArcFace")
    detector_backend = os.getenv("FACE_DETECTOR_BACKEND", "opencv")

    try:
        results = DeepFace.represent(
            img_path=image,
            model_name=model_name,
            detector_backend=detector_backend,
            enforce_detection=True,
            align=True,
        )
        if not results or len(results) != 1:
            raise FaceEngineError("Pastikan hanya satu wajah yang terlihat di kamera.")

        embedding = results[0].get("embedding")
        if not embedding or not isinstance(embedding, (list, tuple)):
            raise FaceEngineError("Model tidak menghasilkan data pengenalan wajah yang valid.")

        return [float(value) for value in embedding]
    except FaceEngineError:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if "face could not be detected" in message or "could not detect" in message:
            raise FaceEngineError(
                "Wajah tidak terdeteksi. Hadapkan wajah ke kamera dan perbaiki pencahayaan."
            ) from exc
        logging.exception("DeepFace gagal menghasilkan embedding")
        raise FaceEngineError(
            "Verifikasi wajah gagal diproses. Coba lagi dengan wajah menghadap kamera. "
            "Periksa terminal Flask untuk detailnya."
        ) from exc


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for two embeddings."""
    if len(left) != len(right) or not left:
        raise FaceEngineError("Data Face Profile tidak sesuai dengan model yang digunakan.")

    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if not norm_left or not norm_right:
        raise FaceEngineError("Embedding wajah tidak valid.")

    return dot / (norm_left * norm_right)


def compare_embedding(data_url: str, stored_embedding_json: str) -> tuple[bool, float]:
    """Compare a live camera embedding with a saved embedding JSON string."""
    try:
        stored = json.loads(stored_embedding_json)
    except (TypeError, ValueError) as exc:
        raise FaceEngineError(
            "Face Profile tersimpan tidak valid. Daftarkan ulang wajah."
        ) from exc

    live_embedding = extract_embedding(data_url)
    try:
        stored_embedding = [float(value) for value in stored]
    except (TypeError, ValueError) as exc:
        raise FaceEngineError(
            "Face Profile tersimpan tidak valid. Daftarkan ulang wajah."
        ) from exc

    threshold = float(os.getenv("FACE_MATCH_THRESHOLD", "0.35"))
    score = cosine_similarity(live_embedding, stored_embedding)
    return score >= threshold, score


def _get_face_mesh_class():
    """Resolve the legacy MediaPipe FaceMesh class or show a specific fix."""
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise FaceEngineError(
            "MediaPipe belum terpasang. Aktifkan virtual environment lalu jalankan "
            "pip install mediapipe==0.10.21"
        ) from exc

    # Preferred access for MediaPipe versions that expose the legacy Solutions API.
    solutions = getattr(mp, "solutions", None)
    face_mesh_module = getattr(solutions, "face_mesh", None) if solutions is not None else None
    face_mesh_class = getattr(face_mesh_module, "FaceMesh", None) if face_mesh_module else None
    if face_mesh_class is not None:
        return face_mesh_class

    # Compatibility fallback for builds that keep the legacy package submodule.
    try:
        from mediapipe.python.solutions.face_mesh import FaceMesh
        return FaceMesh
    except Exception as exc:
        version = getattr(mp, "__version__", "tidak diketahui")
        raise FaceEngineError(
            f"MediaPipe versi {version} tidak menyediakan API FaceMesh lama yang dipakai "
            "modul liveness ini. Di terminal proyek (.venv), jalankan: "
            "python -m pip uninstall -y mediapipe lalu python -m pip install mediapipe==0.10.21. "
            "Setelah itu jalankan ulang aplikasi dan tes dengan scripts/check_face_runtime.py."
        ) from exc


def _face_landmarks(data_url: str):
    """Return MediaPipe Face Mesh landmarks from a single camera frame."""
    image = _decode_data_url(data_url)

    try:
        import cv2
    except ImportError as exc:
        raise FaceEngineError(
            "Komponen liveness memerlukan OpenCV. Jalankan: pip install -r requirements-face.txt"
        ) from exc

    try:
        face_mesh_class = _get_face_mesh_class()
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        with face_mesh_class(
            static_image_mode=True,
            max_num_faces=2,
            refine_landmarks=True,
            min_detection_confidence=0.55,
        ) as mesh:
            result = mesh.process(rgb_image)

        faces = getattr(result, "multi_face_landmarks", None) or []
        if len(faces) != 1:
            raise FaceEngineError(
                "Setiap sampel liveness harus berisi tepat satu wajah. Pastikan wajah terlihat jelas."
            )

        landmarks = getattr(faces[0], "landmark", None)
        if not landmarks or len(landmarks) < 468:
            raise FaceEngineError(
                "Landmark wajah tidak lengkap. Hadapkan wajah ke kamera dan coba lagi."
            )
        return landmarks
    except FaceEngineError:
        raise
    except Exception as exc:
        logging.exception("MediaPipe Face Mesh gagal memproses landmark liveness")
        raise FaceEngineError(
            "Pemeriksaan liveness gagal memproses landmark wajah "
            f"({type(exc).__name__}). Periksa terminal Flask untuk detailnya. "
            "Pastikan versi MediaPipe sesuai, lalu jalankan scripts/check_face_runtime.py."
        ) from exc


def _distance(a, b) -> float:
    return math.hypot(float(a.x) - float(b.x), float(a.y) - float(b.y))


def _eye_aspect_ratio(points, indexes) -> float:
    left, upper_a, upper_b, right, lower_b, lower_a = [points[index] for index in indexes]
    horizontal = _distance(left, right)
    if horizontal <= 1e-8:
        return 0.0
    return (_distance(upper_a, lower_a) + _distance(upper_b, lower_b)) / (2.0 * horizontal)


def _average_eye_aspect_ratio(points) -> float:
    left = _eye_aspect_ratio(points, (33, 160, 158, 133, 153, 144))
    right = _eye_aspect_ratio(points, (362, 385, 387, 263, 373, 380))
    return (left + right) / 2.0


def _yaw_proxy(points) -> float:
    """Approximate normalized nose offset; used for a basic turn challenge only."""
    left_eye, right_eye, nose = points[33], points[263], points[1]
    eye_width = abs(float(right_eye.x) - float(left_eye.x))
    if eye_width <= 1e-6:
        return 0.0
    center = (float(left_eye.x) + float(right_eye.x)) / 2.0
    return (float(nose.x) - center) / eye_width


def verify_blink_liveness(frames: dict) -> None:
    """Require an open-eye sample and a distinctly more closed-eye sample."""
    if not isinstance(frames, dict) or not frames.get("open") or not frames.get("blink"):
        raise FaceEngineError(
            "Challenge kedipan belum lengkap. Ambil sampel mata terbuka lalu mata tertutup saat berkedip."
        )

    open_points = _face_landmarks(frames["open"])
    blink_points = _face_landmarks(frames["blink"])
    open_ear = _average_eye_aspect_ratio(open_points)
    blink_ear = _average_eye_aspect_ratio(blink_points)

    if open_ear < 0.16:
        raise FaceEngineError(
            "Mata belum terlihat terbuka dengan jelas pada sampel awal. Ulangi challenge."
        )
    if not (blink_ear < open_ear * 0.78 and open_ear - blink_ear >= 0.035):
        raise FaceEngineError(
            "Kedipan belum terverifikasi. Ambil sampel kedua saat mata benar-benar tertutup ketika berkedip."
        )


def verify_enrollment_liveness(frames: dict) -> None:
    """Require front, blink, and both-direction head-turn samples for enrollment."""
    required = ("front", "blink", "left", "right")
    if not isinstance(frames, dict) or any(not frames.get(key) for key in required):
        raise FaceEngineError(
            "Pendaftaran wajah memerlukan sampel depan, kedipan, menoleh kiri, dan menoleh kanan."
        )

    front_points = _face_landmarks(frames["front"])
    blink_points = _face_landmarks(frames["blink"])
    left_points = _face_landmarks(frames["left"])
    right_points = _face_landmarks(frames["right"])

    front_ear = _average_eye_aspect_ratio(front_points)
    blink_ear = _average_eye_aspect_ratio(blink_points)
    if front_ear < 0.16 or not (
        blink_ear < front_ear * 0.78 and front_ear - blink_ear >= 0.035
    ):
        raise FaceEngineError(
            "Kedipan belum terverifikasi. Ulangi pendaftaran dan ambil sampel blink saat mata tertutup."
        )

    front_yaw = _yaw_proxy(front_points)
    left_yaw = _yaw_proxy(left_points)
    right_yaw = _yaw_proxy(right_points)
    left_delta = left_yaw - front_yaw
    right_delta = right_yaw - front_yaw

    if (
        abs(left_delta) < 0.025
        or abs(right_delta) < 0.025
        or left_delta * right_delta >= 0
        or abs(left_yaw - right_yaw) < 0.07
    ):
        raise FaceEngineError(
            "Gerakan kepala ke kiri dan kanan belum terverifikasi. Ambil dua sampel menoleh yang lebih jelas."
        )
