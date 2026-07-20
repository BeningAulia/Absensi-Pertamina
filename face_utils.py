import face_recognition

def get_encoding(image_path):
    img = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(img)
    return encodings[0] if encodings else None


def match_face(unknown_encoding, known_encodings_list, tolerance=0.3, max_distance=0.3):
    """
    Mencocokkan encoding wajah tidak dikenal dengan daftar encoding pegawai.
    Parameter:
    - unknown_encoding : encoding dari gambar absensi
    - known_encodings_list : list of (pegawai_id, list_of_encodings)
    - tolerance : untuk compare_faces (default 0.3)
    - max_distance : batas maksimal jarak Euclidean (default 0.3, semakin kecil semakin ketat)
    """
    if unknown_encoding is None:
        return None

    best_id = None
    best_distance = float('inf')

    for pegawai_id, encodings in known_encodings_list:
        distances = face_recognition.face_distance(encodings, unknown_encoding)
        min_dist = min(distances)
        if min_dist < best_distance:
            best_distance = min_dist
            best_id = pegawai_id

    if best_distance <= max_distance:
        return best_id
    return None