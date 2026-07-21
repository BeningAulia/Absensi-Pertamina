from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_from_directory, abort, send_file
from models import db, Pegawai, Absensi, Admin
from werkzeug.security import generate_password_hash, check_password_hash
from telegram_notif import send_telegram, send_telegram_photo
import face_recognition
import cv2
import numpy as np
import base64
import os
from datetime import datetime, date, timedelta
from functools import wraps
from sqlalchemy import func
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///absensi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = 'pertamina-absensi-secret-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024   # 20 MB

db.init_app(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)
os.makedirs('templates', exist_ok=True)

known_faces_cache = []

def refresh_face_cache():
    global known_faces_cache
    pegawai_list = Pegawai.query.filter_by(status='aktif').all()
    known_faces_cache = [(p.id, p.face_encodings) for p in pegawai_list if p.face_encodings]

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Silakan login terlebih dahulu.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def is_ajax():
    return (request.headers.get('X-Requested-With') == 'XMLHttpRequest') or request.is_json

def is_duplicate_face(new_encodings, existing_pegawai_list):
    for pegawai in existing_pegawai_list:
        if not pegawai.face_encodings:
            continue
        for new_enc in new_encodings:
            distances = face_recognition.face_distance(pegawai.face_encodings, new_enc)
            if min(distances) < 0.3:
                return pegawai.nama, pegawai.nip
    return None

@app.route('/')
def index():
    return render_template('index_full.html')

@app.route('/api/absen', methods=['POST'])
def absen():
    data = request.json
    image_b64 = data.get('image')
    lat = data.get('lat')
    lon = data.get('lon')

    if not image_b64:
        return jsonify({'status': 'fail', 'pesan': 'Gambar tidak ditemukan'}), 400

    try:
        img_data = base64.b64decode(image_b64.split(',')[1])
    except:
        return jsonify({'status': 'fail', 'pesan': 'Format gambar tidak valid'}), 400

    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    max_dim = 640
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w*scale), int(h*scale)))
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    unknown_encodings = face_recognition.face_encodings(rgb)
    if not unknown_encodings:
        return jsonify({'status': 'fail', 'pesan': 'Wajah tidak terdeteksi'}), 400

    if not known_faces_cache:
        refresh_face_cache()

    from face_utils import match_face
    matched_id = match_face(unknown_encodings[0], known_faces_cache, tolerance=0.3, max_distance=0.3)
    if not matched_id:
        return jsonify({'status': 'fail', 'pesan': 'Wajah tidak dikenali'}), 401

    pegawai = db.session.get(Pegawai, matched_id)
    if pegawai.status != 'aktif':
        return jsonify({'status': 'fail', 'pesan': 'Akun Anda belum diaktifkan oleh admin.'}), 403

    waktu = datetime.now().strftime("%H:%M:%S %d-%m-%Y")
    absen = Absensi(
        pegawai_id=matched_id,
        latitude=lat,
        longitude=lon,
        lokasi_label="Kantor Pertamina"
    )
    db.session.add(absen)
    db.session.commit()

    notif_status = "tidak dikirim"
    try:
        send_telegram_photo(pegawai.nama, pegawai.nip, waktu, lat, lon, img_data)
        notif_status = "terkirim ke admin (dengan foto)"
    except Exception as e:
        try:
            send_telegram(pegawai.nama, pegawai.nip, waktu, lat, lon)
            notif_status = "terkirim ke admin (teks saja)"
        except Exception as e2:
            notif_status = f"gagal: {str(e2)}"

    return jsonify({
        'status': 'ok',
        'nama': pegawai.nama,
        'nip': pegawai.nip,
        'waktu': waktu,
        'lat': lat,
        'lon': lon,
        'notif_status': notif_status
    })

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        from face_utils import get_encoding
        nama = request.form.get('nama')
        nip = request.form.get('nip')
        files = request.files.getlist('faces')

        if not nama or not nip:
            msg = 'Nama dan NIP wajib diisi.'
            if is_ajax():
                return jsonify({'status': 'error', 'message': msg})
            flash(msg, 'error')
            return render_template('register.html')

        if len(files) < 3:
            msg = 'Minimal 3 foto wajah harus diunggah.'
            if is_ajax():
                return jsonify({'status': 'error', 'message': msg})
            flash(msg, 'error')
            return render_template('register.html')

        ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
        max_size = 5 * 1024 * 1024

        for f in files:
            if f.filename == '':
                continue
            ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
            if ext not in ALLOWED_EXTENSIONS:
                msg = f'File "{f.filename}" tidak diizinkan. Hanya JPG, JPEG, PNG.'
                if is_ajax():
                    return jsonify({'status': 'error', 'message': msg})
                flash(msg, 'error')
                return render_template('register.html')
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(0)
            if size > max_size:
                msg = f'File "{f.filename}" terlalu besar ({round(size/(1024*1024),1)}MB). Maksimal 5MB.'
                if is_ajax():
                    return jsonify({'status': 'error', 'message': msg})
                flash(msg, 'error')
                return render_template('register.html')

        encodings = []
        saved_paths = []
        for f in files:
            if f.filename == '':
                continue
            filename = f"{nip}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{f.filename}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(path)
            enc = get_encoding(path)
            if enc is not None:
                encodings.append(enc)
                saved_paths.append(path)
            else:
                if os.path.exists(path):
                    os.remove(path)

        if len(encodings) < 3:
            msg = 'Wajah tidak terdeteksi di foto.'
            for p in saved_paths:
                if os.path.exists(p):
                    os.remove(p)
            if is_ajax():
                return jsonify({'status': 'error', 'message': msg})
            flash(msg, 'error')
            return render_template('register.html')

        if Pegawai.query.filter_by(nip=nip).first():
            msg = 'NIP sudah terdaftar.'
            for p in saved_paths:
                if os.path.exists(p):
                    os.remove(p)
            if is_ajax():
                return jsonify({'status': 'error', 'message': msg})
            flash(msg, 'error')
            return render_template('register.html')

        existing = Pegawai.query.all()
        duplicate = is_duplicate_face(encodings, existing)
        if duplicate:
            msg = f'Gagal! Wajah terlalu mirip dengan pegawai {duplicate[0]} ({duplicate[1]}).'
            for p in saved_paths:
                if os.path.exists(p):
                    os.remove(p)
            if is_ajax():
                return jsonify({'status': 'error', 'message': msg})
            flash(msg, 'error')
            return render_template('register.html')

        pegawai = Pegawai(
            nama=nama,
            nip=nip,
            face_encodings=encodings,
            uploaded_files=saved_paths,
            status='pending'
        )
        db.session.add(pegawai)
        db.session.commit()

        msg = 'Pendaftaran berhasil! Tunggu persetujuan admin sebelum dapat melakukan absensi.'
        if is_ajax():
            return jsonify({'status': 'success', 'message': msg})
        flash(msg, 'success')
        return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if Admin.query.first():
        msg = 'Admin sudah terdaftar.'
        if is_ajax():
            return jsonify({'status': 'error', 'message': msg})
        flash(msg, 'error')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            msg = 'Username dan password wajib diisi.'
            if is_ajax():
                return jsonify({'status': 'error', 'message': msg})
            flash(msg, 'error')
            return render_template('admin_register.html')

        hashed = generate_password_hash(password)
        admin = Admin(username=username, password_hash=hashed)
        db.session.add(admin)
        db.session.commit()

        msg = 'Akun admin berhasil dibuat!'
        if is_ajax():
            return jsonify({'status': 'success', 'message': msg, 'redirect': url_for('admin_login')})
        flash(msg, 'success')
        return redirect(url_for('admin_login'))

    return render_template('admin_register.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))

    admin_exists = Admin.query.first() is not None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.first()
        if admin and check_password_hash(admin.password_hash, password) and admin.username == username:
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            flash('Login berhasil.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Username atau password salah.', 'error')

    return render_template('admin_login.html', admin_exists=admin_exists)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash('Anda telah logout.', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    search = request.args.get('search', '').strip()

    # Query untuk LOG (tampilkan semua data, 500 terbaru)
    query_log = Absensi.query.order_by(Absensi.waktu.asc()).limit(500)

    # Query untuk PETA (default hanya hari ini, atau sesuai pencarian)
    query_map = Absensi.query.order_by(Absensi.waktu.asc())
    if search:
        try:
            day = datetime.strptime(search, '%Y-%m-%d')
            next_day = day + timedelta(days=1)
            query_map = query_map.filter(Absensi.waktu >= day, Absensi.waktu < next_day)
        except ValueError:
            try:
                month = datetime.strptime(search, '%Y-%m')
                query_map = query_map.filter(func.strftime('%Y-%m', Absensi.waktu) == search)
            except ValueError:
                pass
    else:
        # Default: hanya hari ini
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        query_map = query_map.filter(Absensi.waktu >= today, Absensi.waktu < tomorrow)

    absensi_list = query_log.all()

    # Siapkan data peta
    map_absensi = query_map.limit(500).all()
    map_data = []
    for a in map_absensi:
        map_data.append({
            'nama': a.pegawai.nama if a.pegawai else '',
            'nip': a.pegawai.nip if a.pegawai else '',
            'waktu': a.waktu.strftime('%d/%m/%Y %H:%M') if a.waktu else '',
            'lat': a.latitude,
            'lon': a.longitude
        })

    # Pengelompokan log
    grouped = {}
    for a in absensi_list:
        tgl = a.waktu.date()
        if tgl not in grouped:
            grouped[tgl] = []
        grouped[tgl].append(a)

    grouped_absensi = []
    for tgl in sorted(grouped.keys()):
        grouped_absensi.append({
            'tanggal': tgl,
            'entries': grouped[tgl]
        })

    pegawai_list = Pegawai.query.all()
    pending_list = Pegawai.query.filter_by(status='pending').all()

    return render_template('admin.html',
                           grouped_absensi=grouped_absensi,
                           map_data=map_data,
                           pegawai_list=pegawai_list,
                           pending_list=pending_list,
                           search=search)

@app.route('/admin/download_absensi_harian/<string:tanggal>')
@admin_required
def download_absensi_harian(tanggal):
    try:
        hari = datetime.strptime(tanggal, '%Y-%m-%d')
        next_day = hari + timedelta(days=1)
    except ValueError:
        flash('Format tanggal tidak valid.', 'error')
        return redirect(url_for('admin_dashboard'))

    absensi_list = Absensi.query.filter(
        Absensi.waktu >= hari,
        Absensi.waktu < next_day
    ).order_by(Absensi.waktu.asc()).all()

    if not absensi_list:
        flash(f'Tidak ada data absensi untuk tanggal {tanggal}.', 'info')
        return redirect(url_for('admin_dashboard'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Absensi {tanggal}"

    headers = ['No', 'Nama', 'NIP', 'Waktu', 'Latitude', 'Longitude', 'Lokasi']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="003DA5", end_color="003DA5", fill_type="solid")
        cell.alignment = Alignment(horizontal='center')

    for i, a in enumerate(absensi_list, 1):
        ws.cell(row=i+1, column=1, value=i)
        ws.cell(row=i+1, column=2, value=a.pegawai.nama if a.pegawai else '')
        ws.cell(row=i+1, column=3, value=a.pegawai.nip if a.pegawai else '')
        ws.cell(row=i+1, column=4, value=a.waktu.strftime('%d/%m/%Y %H:%M:%S') if a.waktu else '')
        ws.cell(row=i+1, column=5, value=a.latitude)
        ws.cell(row=i+1, column=6, value=a.longitude)
        ws.cell(row=i+1, column=7, value=a.lokasi_label)

    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 20

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'absensi_{tanggal}.xlsx'
    )

@app.route('/admin/hapus_absensi/<int:id>', methods=['POST'])
@admin_required
def hapus_absensi(id):
    absensi = db.session.get(Absensi, id)
    if not absensi:
        abort(404)
    db.session.delete(absensi)
    db.session.commit()
    flash('Data absensi dihapus.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/hapus_absensi_tanggal/<string:tanggal>', methods=['POST'])
@admin_required
def hapus_absensi_tanggal(tanggal):
    try:
        hari = datetime.strptime(tanggal, '%Y-%m-%d')
        next_day = hari + timedelta(days=1)
    except ValueError:
        flash('Format tanggal tidak valid.', 'error')
        return redirect(url_for('admin_dashboard'))

    deleted_count = Absensi.query.filter(
        Absensi.waktu >= hari,
        Absensi.waktu < next_day
    ).delete()
    db.session.commit()
    flash(f'{deleted_count} data absensi pada {tanggal} berhasil dihapus.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/hapus_pegawai/<int:id>', methods=['POST'])
@admin_required
def hapus_pegawai(id):
    pegawai = db.session.get(Pegawai, id)
    if not pegawai:
        abort(404)

    if pegawai.uploaded_files:
        for file_path in pegawai.uploaded_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Gagal menghapus file {file_path}: {e}")

    db.session.delete(pegawai)
    db.session.commit()
    refresh_face_cache()
    flash('Pegawai dan data absensi terkait dihapus.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/hapus_admin', methods=['POST'])
@admin_required
def hapus_admin():
    admin = Admin.query.first()
    if admin:
        db.session.delete(admin)
        db.session.commit()
        session.clear()
        flash('Admin dihapus. Silakan daftar ulang.', 'info')
        return redirect(url_for('admin_register'))
    flash('Tidak ada admin.', 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/approve_pegawai/<int:id>', methods=['POST'])
@admin_required
def approve_pegawai(id):
    pegawai = db.session.get(Pegawai, id)
    if not pegawai:
        abort(404)
    pegawai.status = 'aktif'
    db.session.commit()
    refresh_face_cache()
    flash(f'Pegawai {pegawai.nama} ({pegawai.nip}) telah diaktifkan.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_pegawai/<int:id>', methods=['POST'])
@admin_required
def reject_pegawai(id):
    pegawai = db.session.get(Pegawai, id)
    if not pegawai:
        abort(404)

    if pegawai.uploaded_files:
        for file_path in pegawai.uploaded_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Gagal menghapus file {file_path}: {e}")

    db.session.delete(pegawai)
    db.session.commit()
    flash(f'Pendaftaran {pegawai.nama} ({pegawai.nip}) ditolak dan dihapus.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve_all', methods=['POST'])
@admin_required
def approve_all():
    pending_pegawai = Pegawai.query.filter_by(status='pending').all()
    if not pending_pegawai:
        flash('Tidak ada pendaftaran yang menunggu.', 'info')
        return redirect(url_for('admin_dashboard'))

    for pegawai in pending_pegawai:
        pegawai.status = 'aktif'
    db.session.commit()
    refresh_face_cache()
    flash(f'{len(pending_pegawai)} pegawai berhasil diaktifkan.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_pegawai/<int:id>', methods=['POST'])
@admin_required
def edit_pegawai(id):
    pegawai = db.session.get(Pegawai, id)
    if not pegawai:
        abort(404)

    nama = request.form.get('nama', '').strip()
    nip = request.form.get('nip', '').strip()

    if not nama or not nip:
        flash('Nama dan NIP tidak boleh kosong.', 'error')
        return redirect(url_for('admin_dashboard'))

    existing = Pegawai.query.filter_by(nip=nip).first()
    if existing and existing.id != pegawai.id:
        flash('NIP sudah digunakan oleh pegawai lain.', 'error')
        return redirect(url_for('admin_dashboard'))

    pegawai.nama = nama
    pegawai.nip = nip
    db.session.commit()

    flash(f'Data pegawai {nama} ({nip}) berhasil diperbarui.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        refresh_face_cache()
    print("\n" + "="*60)
    print(">>> Server berjalan di https://0.0.0.0:5000")
    print("="*60 + "\n")
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000,
        ssl_context=('cert.pem', 'key.pem')
    )
