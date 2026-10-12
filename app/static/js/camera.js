(() => {
  "use strict";

  const video = document.getElementById('cameraVideo');
  const startButton = document.getElementById('startCamera');
  const stopButton = document.getElementById('stopCamera');
  const retryButton = document.getElementById('retryChallenge');
  const consent = document.getElementById('biometricConsent');
  const result = document.getElementById('cameraResult');
  const formTarget = document.getElementById('cameraActionTarget');
  const hiddenPurpose = document.getElementById('cameraPurpose');
  if (!video || !startButton || !formTarget) return;

  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const attendanceModalElement = document.getElementById('attendanceCameraModal');
  const attendanceModal = attendanceModalElement && window.bootstrap
    ? new bootstrap.Modal(attendanceModalElement)
    : null;
  const challengeTitle = document.getElementById('cameraChallengeTitle');
  const challengeText = document.getElementById('cameraChallengeText');

  // Sampel diambil otomatis dari video setelah challenge terdeteksi.
  // Mahasiswa tidak perlu menekan tombol untuk setiap foto/frame.
  const enrollmentSteps = [
    {key: 'front', title: 'Langkah 1 dari 4 · Hadap ke depan', text: 'Hadapkan wajah ke kamera, mata terbuka, dan tahan posisi sebentar. Sistem akan mengambil sampel otomatis.'},
    {key: 'blink', title: 'Langkah 2 dari 4 · Kedipkan mata', text: 'Buka mata, lalu kedipkan sekali secara alami. Sistem mendeteksi perubahan mata dan mengambil sampel otomatis.'},
    {key: 'left', title: 'Langkah 3 dari 4 · Tengok ke kiri', text: 'Tengok kepala ke kiri dan tahan sebentar. Jangan menekan tombol foto.'},
    {key: 'right', title: 'Langkah 4 dari 4 · Tengok ke kanan', text: 'Tengok kepala ke kanan, berlawanan dengan arah sebelumnya, dan tahan sebentar.'}
  ];
  const attendanceSteps = [
    {key: 'open', title: 'Langkah 1 dari 2 · Hadap ke depan', text: 'Hadapkan wajah ke depan dengan mata terbuka. Sistem akan menangkap sampel otomatis.'},
    {key: 'blink', title: 'Langkah 2 dari 2 · Kedipkan mata', text: 'Kedipkan mata sekali saat melihat kamera. Sampel akan diambil otomatis untuk verifikasi.'}
  ];

  let stream = null;
  let faceMesh = null;
  let frames = {};
  let stepIndex = 0;
  let requestInProgress = false;
  let processingFrame = false;
  let frameLoopActive = false;
  let frontEar = null;
  let frontYaw = null;
  let previousEar = null;
  let hasSeenOpenEyes = false;
  let stableFrames = 0;
  let stableSign = 0;
  let leftTurnDelta = null;
  let autoSubmitStarted = false;
  let lastResultMessage = '';
  let lastStatusMessage = '';
  let animationHandle = null;

  function currentPurpose() {
    return hiddenPurpose?.value === 'attendance' ? 'attendance' : 'enroll';
  }

  function stepsForPurpose() {
    return currentPurpose() === 'attendance' ? attendanceSteps : enrollmentSteps;
  }

  function showResult(message, kind = '') {
    if (!result || (message === lastResultMessage && kind === result.dataset.kind)) return;
    lastResultMessage = message;
    result.textContent = message;
    result.className = `camera-result show ${kind}`.trim();
    result.dataset.kind = kind;
  }

  function setChallenge(title, text) {
    if (challengeTitle) challengeTitle.textContent = title;
    if (challengeText) challengeText.textContent = text;
  }

  function updateChallenge() {
    const step = stepsForPurpose()[stepIndex];
    if (step) setChallenge(step.title, step.text);
  }

  function setStatus(message) {
    if (message === lastStatusMessage) return;
    lastStatusMessage = message;
    showResult(message, '');
  }

  function resetChallenge() {
    frames = {};
    stepIndex = 0;
    frontEar = null;
    frontYaw = null;
    previousEar = null;
    hasSeenOpenEyes = false;
    stableFrames = 0;
    stableSign = 0;
    leftTurnDelta = null;
    autoSubmitStarted = false;
    requestInProgress = false;
    lastStatusMessage = '';
    retryButton?.classList.add('d-none');
    updateChallenge();
  }

  function stopTracksAndMesh() {
    frameLoopActive = false;
    processingFrame = false;
    if (animationHandle !== null) cancelAnimationFrame(animationHandle);
    animationHandle = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    if (faceMesh) {
      try { faceMesh.close(); } catch (_) { /* best-effort cleanup */ }
    }
    faceMesh = null;
    video.srcObject = null;
    video.classList.add('d-none');
    document.getElementById('cameraPlaceholder')?.classList.remove('d-none');
    stopButton?.classList.add('d-none');
    startButton.classList.remove('d-none');
  }

  function stopCamera() {
    stopTracksAndMesh();
    resetChallenge();
    if (result) {
      result.className = 'camera-result';
      result.textContent = '';
      delete result.dataset.kind;
    }
    lastResultMessage = '';
  }

  function captureCurrentFrame() {
    if (!video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
      throw new Error('Frame kamera belum siap. Pertahankan wajah di dalam bingkai.');
    }
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d', {willReadFrequently: true});
    if (!context) throw new Error('Browser tidak dapat membuat sampel kamera.');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.90);
  }

  function pointDistance(a, b) {
    return Math.hypot(Number(a.x) - Number(b.x), Number(a.y) - Number(b.y));
  }

  function eyeAspectRatio(points, indexes) {
    const [left, upperA, upperB, right, lowerB, lowerA] = indexes.map((index) => points[index]);
    const horizontal = pointDistance(left, right);
    if (horizontal <= 1e-8) return 0;
    return (pointDistance(upperA, lowerA) + pointDistance(upperB, lowerB)) / (2 * horizontal);
  }

  function averageEar(points) {
    const left = eyeAspectRatio(points, [33, 160, 158, 133, 153, 144]);
    const right = eyeAspectRatio(points, [362, 385, 387, 263, 373, 380]);
    return (left + right) / 2;
  }

  function yawProxy(points) {
    const leftEye = points[33];
    const rightEye = points[263];
    const nose = points[1];
    const eyeWidth = Math.abs(Number(rightEye.x) - Number(leftEye.x));
    if (eyeWidth <= 1e-6) return 0;
    const eyeCenter = (Number(leftEye.x) + Number(rightEye.x)) / 2;
    return (Number(nose.x) - eyeCenter) / eyeWidth;
  }

  function advanceStep(message) {
    stepIndex += 1;
    stableFrames = 0;
    stableSign = 0;
    previousEar = null;
    updateChallenge();
    if (message) setStatus(message);
    if (stepIndex >= stepsForPurpose().length) {
      setChallenge('Challenge selesai · Memverifikasi', 'Sampel telah direkam otomatis. Sistem sedang memverifikasi challenge dan identitas di server.');
      void submitSamples();
    }
  }

  function processChallenge(points) {
    if (requestInProgress || autoSubmitStarted) return;
    const key = stepsForPurpose()[stepIndex]?.key;
    if (!key) return;

    const ear = averageEar(points);
    const yaw = yawProxy(points);
    if (!Number.isFinite(ear) || !Number.isFinite(yaw)) {
      stableFrames = 0;
      setStatus('Landmark belum stabil. Hadapkan wajah ke kamera dan pastikan pencahayaan cukup.');
      return;
    }

    if (key === 'front' || key === 'open') {
      const frontal = Math.abs(yaw) <= 0.075;
      const eyesOpen = ear >= 0.16;
      if (frontal && eyesOpen) {
        stableFrames += 1;
        setStatus(`Wajah terdeteksi. Pertahankan posisi... ${Math.min(stableFrames, 8)}/8`);
        if (stableFrames >= 8) {
          try {
            frames[key] = captureCurrentFrame();
            if (key === 'front') {
              frontEar = ear;
              frontYaw = yaw;
              stepIndex += 1;
              stableFrames = 0;
              previousEar = ear;
              hasSeenOpenEyes = true;
              updateChallenge();
              setStatus('Sampel wajah depan terekam otomatis. Sekarang ikuti instruksi kedipan.');
            } else {
              frontEar = ear;
              stepIndex += 1;
              stableFrames = 0;
              previousEar = ear;
              hasSeenOpenEyes = true;
              updateChallenge();
              setStatus('Sampel mata terbuka terekam. Sekarang kedipkan mata satu kali.');
            }
          } catch (error) {
            stableFrames = 0;
            setStatus(error.message || 'Gagal mengambil frame kamera.');
          }
        }
      } else {
        stableFrames = 0;
        setStatus(!frontal ? 'Hadapkan wajah lebih lurus ke kamera.' : 'Buka mata dan lihat ke kamera.');
      }
      return;
    }

    if (key === 'blink') {
      if (ear >= Math.max(0.16, (frontEar || 0.2) * 0.84)) {
        hasSeenOpenEyes = true;
      }
      const closedEnough = frontEar !== null && ear < frontEar * 0.72 && (frontEar - ear) >= 0.035;
      const transitionedFromOpen = previousEar !== null && previousEar > frontEar * 0.80;
      if (hasSeenOpenEyes && closedEnough && transitionedFromOpen) {
        try {
          frames.blink = captureCurrentFrame();
          if (currentPurpose() === 'attendance') {
            stepIndex += 1;
            updateChallenge();
            setStatus('Kedipan terdeteksi otomatis. Mengirim verifikasi presensi...');
            void submitSamples();
          } else {
            advanceStepAfterBlink();
          }
          previousEar = ear;
          return;
        } catch (error) {
          setStatus(error.message || 'Gagal mengambil sampel kedipan.');
        }
      }
      previousEar = ear;
      setStatus(closedEnough ? 'Kedipan terdeteksi. Menyimpan sampel...' : 'Kedipkan mata satu kali secara alami.');
      return;
    }

    const delta = yaw - frontYaw;
    const magnitudeEnough = Math.abs(delta) >= 0.045;
    if (key === 'left') {
      if (magnitudeEnough) {
        const sign = Math.sign(delta);
        stableFrames = sign === stableSign ? stableFrames + 1 : 1;
        stableSign = sign;
        setStatus(`Gerakan kepala terdeteksi. Tahan posisi... ${Math.min(stableFrames, 5)}/5`);
        if (stableFrames >= 5) {
          try {
            frames.left = captureCurrentFrame();
            leftTurnDelta = delta;
            advanceStep('Sampel gerakan kepala pertama terekam. Sekarang tengok ke sisi berlawanan.');
          } catch (error) {
            stableFrames = 0;
            setStatus(error.message || 'Gagal mengambil sampel gerakan kepala.');
          }
        }
      } else {
        stableFrames = 0;
        stableSign = 0;
        setStatus('Tengok kepala ke kiri dengan jelas dan tahan sebentar.');
      }
      return;
    }

    if (key === 'right') {
      const oppositeDirection = leftTurnDelta !== null && delta * leftTurnDelta < 0;
      const separationEnough = leftTurnDelta !== null && Math.abs(delta - leftTurnDelta) >= 0.07;
      if (magnitudeEnough && oppositeDirection && separationEnough) {
        const sign = Math.sign(delta);
        stableFrames = sign === stableSign ? stableFrames + 1 : 1;
        stableSign = sign;
        setStatus(`Gerakan sisi berlawanan terdeteksi. Tahan posisi... ${Math.min(stableFrames, 5)}/5`);
        if (stableFrames >= 5) {
          try {
            frames.right = captureCurrentFrame();
            stepIndex += 1;
            updateChallenge();
            setStatus('Semua sampel pendaftaran terekam otomatis. Memverifikasi...');
            void submitSamples();
          } catch (error) {
            stableFrames = 0;
            setStatus(error.message || 'Gagal mengambil sampel gerakan kepala.');
          }
        }
      } else {
        stableFrames = 0;
        stableSign = 0;
        setStatus('Tengok ke kanan, berlawanan dengan arah sebelumnya, lalu tahan sebentar.');
      }
    }
  }

  function advanceStepAfterBlink() {
    stepIndex += 1;
    stableFrames = 0;
    stableSign = 0;
    previousEar = null;
    updateChallenge();
    setStatus('Kedipan terverifikasi secara awal. Sekarang tengok ke kiri.');
  }

  async function submitSamples() {
    const purpose = currentPurpose();
    if (requestInProgress || autoSubmitStarted) return;
    const endpoint = formTarget.dataset.endpoint;
    if (!endpoint) {
      showResult('Endpoint verifikasi tidak ditemukan. Muat ulang halaman.', 'error');
      retryButton?.classList.remove('d-none');
      return;
    }
    if (purpose === 'enroll' && consent && !consent.checked) {
      showResult('Centang persetujuan pemrosesan data biometrik sebelum melanjutkan.', 'error');
      retryButton?.classList.remove('d-none');
      return;
    }
    const token = formTarget.dataset.token || '';
    if (purpose === 'attendance' && !token) {
      showResult('Token sesi tidak tersedia. Scan QR dosen atau masukkan token sesi terlebih dahulu.', 'error');
      retryButton?.classList.remove('d-none');
      return;
    }
    const required = purpose === 'attendance' ? ['open', 'blink'] : ['front', 'blink', 'left', 'right'];
    if (required.some((key) => !frames[key])) {
      showResult('Challenge belum lengkap. Pilih ulangi challenge dan ikuti semua instruksi.', 'error');
      retryButton?.classList.remove('d-none');
      return;
    }

    requestInProgress = true;
    autoSubmitStarted = true;
    if (startButton) startButton.disabled = true;
    if (stopButton) stopButton.disabled = true;
    setChallenge('Sedang memverifikasi...', 'Jangan tutup halaman. Sampel diperiksa di server sebelum Face Profile atau kehadiran disimpan.');
    showResult('Memverifikasi liveness dan kecocokan wajah di server. Proses pertama dapat membutuhkan waktu lebih lama.', '');

    try {
      const payload = {
        image: frames.front || frames.open,
        frames,
        token,
        consent: consent ? consent.checked : purpose === 'attendance'
      };
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
        body: JSON.stringify(payload),
        credentials: 'same-origin'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.message || 'Permintaan gagal. Silakan coba kembali.');
      showResult(data.message + (data.status_label ? ` Status: ${data.status_label}. Waktu: ${data.time}.` : ''), 'success');
      setChallenge('Berhasil', 'Proses selesai. Halaman akan diperbarui.');
      stopTracksAndMesh();
      if (retryButton) retryButton.classList.add('d-none');
      setTimeout(() => window.location.reload(), 1600);
    } catch (error) {
      autoSubmitStarted = false;
      requestInProgress = false;
      frameLoopActive = false;
      if (animationHandle !== null) cancelAnimationFrame(animationHandle);
      animationHandle = null;
      if (startButton) startButton.disabled = false;
      if (stopButton) stopButton.disabled = false;
      frames = {};
      stepIndex = 0;
      frontEar = null;
      frontYaw = null;
      previousEar = null;
      hasSeenOpenEyes = false;
      stableFrames = 0;
      stableSign = 0;
      leftTurnDelta = null;
      updateChallenge();
      showResult(`${error.message || 'Proses gagal.'} Tekan "Ulangi Challenge" untuk mencoba kembali.`, 'error');
      retryButton?.classList.remove('d-none');
    } finally {
      requestInProgress = false;
    }
  }

  async function startFaceMesh() {
    if (typeof window.FaceMesh !== 'function') {
      throw new Error('Modul Face Mesh browser belum termuat. Periksa koneksi internet, lalu muat ulang halaman.');
    }
    const mesh = new window.FaceMesh({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@0.4.1633559619/${file}`
    });
    mesh.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.60,
      minTrackingConfidence: 0.60
    });
    mesh.onResults((output) => {
      const faces = output.multiFaceLandmarks || [];
      if (faces.length !== 1) {
        stableFrames = 0;
        stableSign = 0;
        setStatus(faces.length === 0
          ? 'Wajah belum terdeteksi. Posisikan wajah di dalam bingkai dan perbaiki pencahayaan.'
          : 'Terdeteksi lebih dari satu wajah. Pastikan hanya wajah Anda yang terlihat.');
        return;
      }
      const points = faces[0];
      if (!Array.isArray(points) || points.length < 468) {
        stableFrames = 0;
        setStatus('Landmark wajah belum lengkap. Tetap hadapkan wajah ke kamera.');
        return;
      }
      processChallenge(points);
    });
    faceMesh = mesh;
  }

  async function frameLoop() {
    if (!frameLoopActive || !stream || !faceMesh) return;
    if (!processingFrame && video.readyState >= 2) {
      processingFrame = true;
      try {
        await faceMesh.send({image: video});
      } catch (error) {
        frameLoopActive = false;
        showResult(`Pemrosesan landmark browser gagal: ${error.message || 'kesalahan tidak diketahui'}. Periksa koneksi dan muat ulang halaman.`, 'error');
        retryButton?.classList.remove('d-none');
      } finally {
        processingFrame = false;
      }
    }
    if (frameLoopActive) animationHandle = requestAnimationFrame(frameLoop);
  }

  document.querySelectorAll('[data-start-attendance]').forEach((button) => {
    button.addEventListener('click', () => {
      formTarget.dataset.endpoint = button.dataset.endpoint || '';
      formTarget.dataset.token = button.dataset.token || '';
      if (hiddenPurpose) hiddenPurpose.value = 'attendance';
      const title = document.getElementById('attendanceCourseName');
      if (title) title.textContent = button.dataset.course || 'Hadapkan wajah ke kamera';
      stopCamera();
      updateChallenge();
      if (result) result.className = 'camera-result';
      if (attendanceModal) attendanceModal.show();
    });
  });
  attendanceModalElement?.addEventListener('hidden.bs.modal', stopCamera);

  startButton.addEventListener('click', async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Browser tidak mendukung akses kamera. Gunakan browser modern dan HTTPS atau localhost.');
      }
      resetChallenge();
      if (result) result.className = 'camera-result';
      lastResultMessage = '';
      stream = await navigator.mediaDevices.getUserMedia({
        video: {facingMode: 'user', width: {ideal: 640}, height: {ideal: 480}},
        audio: false
      });
      video.srcObject = stream;
      video.classList.remove('d-none');
      document.getElementById('cameraPlaceholder')?.classList.add('d-none');
      await video.play();
      await startFaceMesh();
      startButton.classList.add('d-none');
      stopButton?.classList.remove('d-none');
      if (stopButton) stopButton.disabled = false;
      frameLoopActive = true;
      animationHandle = requestAnimationFrame(frameLoop);
      setStatus('Kamera aktif. Pendaftaran dan pengambilan sampel berjalan otomatis; ikuti instruksi di layar.');
    } catch (error) {
      stopTracksAndMesh();
      showResult(error.message || 'Kamera atau modul Face Mesh tidak dapat diakses.', 'error');
      retryButton?.classList.remove('d-none');
    }
  });

  stopButton?.addEventListener('click', stopCamera);
  retryButton?.addEventListener('click', () => {
    resetChallenge();
    if (stream && faceMesh) {
      frameLoopActive = true;
      if (!processingFrame) animationHandle = requestAnimationFrame(frameLoop);
      retryButton.classList.add('d-none');
      setStatus('Challenge diulang. Ikuti instruksi; sampel akan direkam otomatis.');
    } else {
      retryButton.classList.add('d-none');
      showResult('Klik Aktifkan Kamera untuk memulai challenge baru.', '');
    }
  });

  updateChallenge();
  window.addEventListener('beforeunload', stopTracksAndMesh);
})();
