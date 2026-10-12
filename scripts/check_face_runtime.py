"""Diagnostic for OpenCV + MediaPipe legacy FaceMesh used by liveness checks.

Run from the project root with the project's virtual environment activated:
    python scripts/check_face_runtime.py
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    try:
        import cv2
        import mediapipe as mp
        import numpy as np
        from app.face_engine import _get_face_mesh_class

        print(f"Python: {sys.version.split()[0]}")
        print(f"OpenCV: {cv2.__version__}")
        print(f"MediaPipe: {getattr(mp, '__version__', 'versi tidak diketahui')}")
        face_mesh_class = _get_face_mesh_class()
        # A blank test frame should return zero faces; this diagnostic tests that the graph initializes.
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with face_mesh_class(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.55,
        ) as mesh:
            result = mesh.process(cv2.cvtColor(test_frame, cv2.COLOR_BGR2RGB))
        face_count = len(getattr(result, 'multi_face_landmarks', None) or [])
        print(f"FaceMesh: berhasil diinisialisasi dan memproses frame tes (wajah terdeteksi={face_count}; 0 diharapkan pada gambar kosong).")
        print("Runtime vision siap. Berikutnya, uji liveness dengan wajah asli di aplikasi.")
        return 0
    except Exception as exc:
        print(f"DIAGNOSTIK GAGAL: {type(exc).__name__}: {exc}")
        print("Coba pasang ulang paket yang dipatok dengan langkah di README, lalu jalankan tes ini lagi.")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
