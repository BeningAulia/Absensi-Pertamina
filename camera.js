document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const snapBtn = document.getElementById('snap');
    const statusDiv = document.getElementById('status');
    let stream = null;
    let isSubmitting = false;

    if (!window.isSecureContext) {
        showToast('⚠️ Halaman harus diakses melalui localhost atau HTTPS', 'error');
        if (snapBtn) snapBtn.disabled = true;
        return;
    }

    async function initKamera() {
        const resolutions = [
            { width: 1920, height: 1080 },
            { width: 1280, height: 720 },
            { width: 640, height: 480 },
            { width: 320, height: 240 }
        ];

        let lastError = null;
        for (const { width, height } of resolutions) {
            try {
                const constraints = {
                    video: {
                        width: { ideal: width },
                        height: { ideal: height },
                        facingMode: 'user'
                    }
                };
                stream = await navigator.mediaDevices.getUserMedia(constraints);
                video.srcObject = stream;
                await video.play();
                console.log(`[Kamera] Resolusi berhasil: ${video.videoWidth}x${video.videoHeight}`);
                return;
            } catch (err) {
                lastError = err;
            }
        }
        showToast('📷 Kamera tidak tersedia atau izin ditolak', 'error');
        if (snapBtn) snapBtn.disabled = true;
        throw lastError;
    }

    function ambilSnapshot() {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        // Balik horizontal agar foto tidak mirror
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0);
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        return canvas.toDataURL('image/jpeg', 0.92);
    }

    function dapatkanLokasi() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) return reject(new Error('Geolokasi tidak didukung'));
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
                (err) => reject(new Error('Gagal mendapatkan lokasi. Pastikan izin lokasi diberikan.')),
                { enableHighAccuracy: true, timeout: 10000 }
            );
        });
    }

    async function kirimAbsensi(imageData, lat, lon) {
        const res = await fetch('/api/absen', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData, lat, lon })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.pesan || 'Gagal');
        return data;
    }

    function tampilkanStatus(tipe, pesan) {
        if (statusDiv) {
            statusDiv.innerHTML = `<div class="flash-message ${tipe}">${pesan}</div>`;
            const fm = statusDiv.querySelector('.flash-message');
            if (fm) {
                setTimeout(() => fm.classList.add('fade-out'), 4000);
                setTimeout(() => { if (fm.parentNode) fm.remove(); }, 4500);
            }
        }
    }

    function setLoading(aktif) {
        isSubmitting = aktif;
        if (snapBtn) {
            snapBtn.disabled = aktif;
            snapBtn.innerHTML = aktif
                ? '<i class="fas fa-spinner fa-pulse"></i> Memproses...'
                : '<i class="fas fa-camera"></i> Ambil Absen';
        }
    }

    if (snapBtn) {
        snapBtn.addEventListener('click', async () => {
            if (isSubmitting) return;
            if (!stream || video.readyState < 2) {
                showToast('📷 Kamera belum siap. Tunggu sebentar.', 'warning');
                return;
            }

            setLoading(true);
            tampilkanStatus('info', '⌛ Mendeteksi wajah dan lokasi...');

            try {
                const imageData = ambilSnapshot();
                const lokasi = await dapatkanLokasi();
                const hasil = await kirimAbsensi(imageData, lokasi.lat, lokasi.lon);

                const mapsLink = `https://maps.google.com/?q=${lokasi.lat},${lokasi.lon}`;
                const toastMessage = `
                    <div style="text-align:left; line-height:1.6;">
                        <div style="font-weight:700; margin-bottom:6px;">✅ Absensi Berhasil</div>
                        <div>👤 <b>Nama</b> : ${hasil.nama}</div>
                        <div>🆔 <b>NIP</b> &nbsp;&nbsp; : ${hasil.nip}</div>
                        <div>🕒 <b>Jam</b> &nbsp;&nbsp; : ${hasil.waktu}</div>
                        <div>📍 <b>Lokasi</b> : <a href="${mapsLink}" target="_blank" style="color:#fff; text-decoration:underline;">Lihat Maps</a></div>
                        ${hasil.notif_status === 'terkirim ke admin (dengan foto)' ? '<div style="margin-top:4px;">📩 Notifikasi + foto terkirim ke admin</div>' : ''}
                    </div>
                `;
                showToast(toastMessage, 'success');
                tampilkanStatus('success', `✅ Selamat datang, ${hasil.nama}!`);
            } catch (err) {
                showToast('❌ ' + err.message, 'error');
                tampilkanStatus('error', '❌ ' + err.message);
            } finally {
                setLoading(false);
            }
        });
    }

    window.addEventListener('beforeunload', () => {
        if (stream) stream.getTracks().forEach(track => track.stop());
    });

    initKamera();
});