from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Pegawai(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    nip = db.Column(db.String(20), unique=True, nullable=False)
    face_encodings = db.Column(db.PickleType)
    uploaded_files = db.Column(db.PickleType)
    status = db.Column(db.String(20), default='pending')   # 'pending' atau 'aktif'
    absensi = db.relationship('Absensi', backref='pegawai', lazy=True, cascade='all, delete-orphan')

class Absensi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pegawai_id = db.Column(db.Integer, db.ForeignKey('pegawai.id'), nullable=False)
    waktu = db.Column(db.DateTime, default=datetime.now)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    lokasi_label = db.Column(db.String(200))

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)