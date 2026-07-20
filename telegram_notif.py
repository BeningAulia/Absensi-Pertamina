import requests

# Token Bot Telegram
TELEGRAM_BOT_TOKEN = "8615936757:AAHHnkk1LzVGLat-cb0zyYPIinlBjwQ2dIM"

# Chat ID Admin (fallback)
ADMIN_CHAT_ID = "7241428393"

# Chat ID Grup (Diperoleh dari getUpdates)
GROUP_CHAT_ID = "-5286297405"


def get_target_chat():
    """Mengembalikan chat ID tujuan (grup jika ada, jika tidak admin pribadi)."""
    if GROUP_CHAT_ID:
        return GROUP_CHAT_ID
    return ADMIN_CHAT_ID


def send_telegram(nama, nip, waktu, lat, lon):
    """
    Kirim notifikasi absensi teks ke target chat (grup/admin).
    """
    target_chat = get_target_chat()

    if not TELEGRAM_BOT_TOKEN:
        print("[ERROR] Token bot tidak dikonfigurasi")
        return False

    if not target_chat:
        print("[ERROR] Chat ID target tidak diatur")
        return False

    print(f"[INFO] Token: {TELEGRAM_BOT_TOKEN[:15]}...{TELEGRAM_BOT_TOKEN[-5:]}")
    print(f"[INFO] Chat ID tujuan: {target_chat}")
    print(f"[INFO] Pegawai: {nama} (NIP: {nip})")
    print(f"[INFO] Waktu: {waktu}")

    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    message = (
        "🔔 <b>ABSENSI PEGAWAI</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Nama</b> : {nama}\n"
        f"🆔 <b>NIP</b>     : {nip}\n"
        f"🕒 <b>Jam</b>     : {waktu}\n"
        f"📍 <b>Lokasi</b> : <a href='{maps_link}'>Lihat di Maps</a>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<i>✅ Absensi tercatat otomatis</i>"
    )

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        result = response.json()
        if result.get("ok"):
            print("[SUKSES] Notifikasi teks terkirim ke grup!")
            return True
        else:
            print(f"[GAGAL] {result.get('description')}")
            return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def send_telegram_photo(nama, nip, waktu, lat, lon, image_bytes):
    """
    Kirim foto absensi ke Telegram dengan caption info.
    image_bytes: byte string gambar JPEG/PNG.
    """
    target_chat = get_target_chat()

    if not TELEGRAM_BOT_TOKEN or not target_chat:
        print("[ERROR] Token/Chat ID tidak diatur")
        return False

    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    caption = (
        "🔔 <b>ABSENSI PEGAWAI</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Nama</b> : {nama}\n"
        f"🆔 <b>NIP</b>     : {nip}\n"
        f"🕒 <b>Jam</b>     : {waktu}\n"
        f"📍 <b>Lokasi</b> : <a href='{maps_link}'>Lihat di Maps</a>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<i>✅ Absensi tercatat otomatis</i>"
    )

    files = {'photo': ('absensi.jpg', image_bytes, 'image/jpeg')}
    data = {
        'chat_id': target_chat,
        'caption': caption,
        'parse_mode': 'HTML'
    }

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        response = requests.post(api_url, data=data, files=files, timeout=15)
        result = response.json()
        if result.get("ok"):
            print("[SUKSES] Foto absensi terkirim ke grup!")
            return True
        else:
            print(f"[GAGAL] {result.get('description')}")
            return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False