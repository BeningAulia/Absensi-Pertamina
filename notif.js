const Notifikasi = (() => {
    async function mintaIzin() {
        if (!('Notification' in window)) return false;
        if (Notification.permission === 'granted') return true;
        if (Notification.permission !== 'denied') {
            const izin = await Notification.requestPermission();
            return izin === 'granted';
        }
        return false;
    }

    function tampilkan(judul, opsi = {}) {
        if (!('Notification' in window)) return;
        if (Notification.permission === 'granted') {
            const notif = new Notification(judul, {
                icon: opsi.icon || '/static/logo-pertamina.png',
                body: opsi.body || '',
                tag: opsi.tag || 'absensi-pertamina',
                requireInteraction: opsi.requireInteraction || false,
                ...opsi
            });
            notif.onclick = () => {
                window.focus();
                notif.close();
                if (opsi.url) window.open(opsi.url, '_blank');
            };
        }
    }

    function notifAbsenSukses(data) {
        tampilkan('✅ Absensi Berhasil', {
            body: `Halo ${data.nama} (${data.nip}), absen tercatat pukul ${data.waktu}`,
            tag: 'absen-sukses'
        });
    }

    return { mintaIzin, tampilkan, notifAbsenSukses };
})();