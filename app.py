# =====================================================================
#   APLIKASI WEB REKOMENDASI FILM DENGAN METODE SAW (VERSI FINAL LENGKAP)
#   Fitur: CRUD Film, CRUD Kriteria, Perhitungan SAW Dinamis
# =====================================================================

from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector

# 1. Inisialisasi Aplikasi Flask
app = Flask(__name__)
app.secret_key = 'kunci_rahasia_proyek_film_saw_paling_final'

# 2. Konfigurasi Database
# Pastikan nama database sesuai dengan yang Anda gunakan
DB_CONFIG = {'host': 'localhost', 'user': 'root', 'password': '', 'database': 'bioskop'}

# 3. Fungsi Helper untuk Koneksi Database
def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# 4. Skala Nilai untuk Konversi Kriteria Kualitatif
GENRE_SCORES = {'Aksi': 4, 'Komedi': 5, 'Horor': 3, 'Sci-Fi': 4, 'Animasi': 5, 'Drama': 3}
UMUR_SCORES = {'SU': 5, '13+': 4, '17+': 3}


# =======================================================
#       ROUTE UTAMA: KALKULATOR SAW DINAMIS
# =======================================================
@app.route('/')
def index():
    conn = get_db_connection()
    if not conn:
        flash('Koneksi database gagal.', 'danger')
        return render_template('index.html')

    hasil_saw = None
    langkah_perhitungan = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM kriteria ORDER BY id_kriteria")
        kriteria_list = cursor.fetchall()
        cursor.execute("SELECT * FROM film")
        film_list = cursor.fetchall()

        if not kriteria_list or not film_list:
            flash('Data film atau kriteria masih kosong. Harap lengkapi data di halaman kelola.', 'warning')
            return render_template('index.html', hasil=None)

        # Langkah 1: Proses data film untuk mengubah nilai kualitatif menjadi kuantitatif
        processed_films = []
        for film in film_list:
            film_copy = film.copy()
            # Konversi genre dan umur ke skor numerik
            if 'genre' in film_copy: film_copy['genre'] = GENRE_SCORES.get(film_copy['genre'], 0)
            if 'kesesuaian_umur' in film_copy: film_copy['kesesuaian_umur'] = UMUR_SCORES.get(film_copy['kesesuaian_umur'], 0)
            processed_films.append(film_copy)
        
        # Simpan Matriks Keputusan (X) untuk ditampilkan
        langkah_perhitungan = {'matriks_keputusan': processed_films}

        # Langkah 2: Normalisasi Matriks secara Dinamis
        matriks_normalisasi = []
        for film in processed_films:
            row_normalisasi = {'id': film['id'], 'judul': film['judul']}
            for kriteria in kriteria_list:
                kolom = kriteria['kolom_film']
                tipe = kriteria['tipe']
                nilai_film = float(film.get(kolom, 0) or 0)
                
                # Dapatkan semua nilai dari kolom ini untuk mencari min/max
                all_values = [float(f.get(kolom, 0) or 0) for f in processed_films if f.get(kolom) is not None]
                if not all_values: all_values = [0]
                
                if tipe == 'benefit':
                    max_val = max(all_values)
                    row_normalisasi[kolom] = nilai_film / max_val if max_val > 0 else 0
                else:  # tipe == 'cost'
                    min_val = min(all_values)
                    row_normalisasi[kolom] = min_val / nilai_film if nilai_film > 0 else 0
            matriks_normalisasi.append(row_normalisasi)
        
        # Simpan Matriks Normalisasi (R) untuk ditampilkan
        langkah_perhitungan['matriks_normalisasi'] = matriks_normalisasi
        langkah_perhitungan['kriteria_list'] = kriteria_list

        # Langkah 3: Perhitungan Skor Preferensi (V) dan Perankingan
        hasil_akhir = []
        for i, film in enumerate(film_list):
            skor = 0
            norm_row = matriks_normalisasi[i]
            for kriteria in kriteria_list:
                bobot = float(kriteria['bobot'])
                kolom = kriteria['kolom_film']
                skor += bobot * norm_row[kolom]
            hasil_akhir.append({'id': film['id'], 'judul': film['judul'], 'skor': skor})

        hasil_saw = sorted(hasil_akhir, key=lambda x: x['skor'], reverse=True)

    except Exception as e:
        flash(f"Terjadi error saat perhitungan: {e}", 'danger')
        hasil_saw = None
    finally:
        if conn and conn.is_connected():
            conn.close()
            
    return render_template('index.html', hasil=hasil_saw, langkah=langkah_perhitungan)

# =======================================================
#               FUNGSI CRUD UNTUK KRITERIA
# =======================================================
@app.route('/kriteria')
def kelola_kriteria():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM kriteria ORDER BY id_kriteria")
    kriteria = cursor.fetchall()
    total_bobot = sum(float(k['bobot']) for k in kriteria)
    conn.close()
    return render_template('kelola_kriteria.html', kriteria=kriteria, total_bobot=total_bobot)

@app.route('/kriteria/tambah', methods=['GET', 'POST'])
def tambah_kriteria():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO kriteria (nama_kriteria, bobot, tipe, kolom_film) VALUES (%s, %s, %s, %s)"
        data = (request.form['nama_kriteria'], request.form['bobot'], request.form['tipe'], request.form['kolom_film'])
        cursor.execute(query, data)
        conn.commit()
        conn.close()
        flash('Kriteria baru berhasil ditambahkan!', 'success')
        return redirect(url_for('kelola_kriteria'))
    return render_template('form_kriteria.html', title='Tambah Kriteria Baru', k=None)

@app.route('/kriteria/edit/<int:id>', methods=['GET', 'POST'])
def edit_kriteria(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        query = "UPDATE kriteria SET nama_kriteria=%s, bobot=%s, tipe=%s WHERE id_kriteria=%s"
        data = (request.form['nama_kriteria'], request.form['bobot'], request.form['tipe'], id)
        cursor.execute(query, data)
        conn.commit()
        conn.close()
        flash('Kriteria berhasil diperbarui!', 'info')
        return redirect(url_for('kelola_kriteria'))
    cursor.execute("SELECT * FROM kriteria WHERE id_kriteria = %s", (id,))
    kriteria = cursor.fetchone()
    conn.close()
    return render_template('form_kriteria.html', title='Edit Kriteria', k=kriteria)

@app.route('/kriteria/hapus/<int:id>')
def hapus_kriteria(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kriteria WHERE id_kriteria = %s", (id,))
    conn.commit()
    conn.close()
    flash('Kriteria telah berhasil dihapus.', 'danger')
    return redirect(url_for('kelola_kriteria'))

# =======================================================
#               FUNGSI CRUD UNTUK FILM
# =======================================================
@app.route('/film')
def kelola_film():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM film ORDER BY id DESC")
    films = cursor.fetchall()
    conn.close()
    return render_template('kelola_film.html', films=films)

@app.route('/film/tambah', methods=['GET', 'POST'])
def tambah_film():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO film (judul, genre, kesesuaian_umur, harga_tiket, review_penonton, skor_cuplikan) VALUES (%s, %s, %s, %s, %s, %s)"
        harga = request.form['harga_tiket'] if request.form['harga_tiket'] else None
        data = (request.form['judul'], request.form['genre'], request.form['kesesuaian_umur'], harga, request.form['review_penonton'], request.form['skor_cuplikan'])
        cursor.execute(query, data)
        conn.commit()
        conn.close()
        flash('Film baru berhasil ditambahkan!', 'success')
        return redirect(url_for('kelola_film'))
    return render_template('form_film.html', title='Tambah Film Baru', film=None)

@app.route('/film/edit/<int:id>', methods=['GET', 'POST'])
def edit_film(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        query = "UPDATE film SET judul=%s, genre=%s, kesesuaian_umur=%s, harga_tiket=%s, review_penonton=%s, skor_cuplikan=%s WHERE id=%s"
        harga = request.form['harga_tiket'] if request.form['harga_tiket'] else None
        data = (request.form['judul'], request.form['genre'], request.form['kesesuaian_umur'], harga, request.form['review_penonton'], request.form['skor_cuplikan'], id)
        cursor.execute(query, data)
        conn.commit()
        conn.close()
        flash('Data film berhasil diperbarui!', 'info')
        return redirect(url_for('kelola_film'))
    cursor.execute("SELECT * FROM film WHERE id = %s", (id,))
    film = cursor.fetchone()
    conn.close()
    return render_template('form_film.html', title='Edit Data Film', film=film)

@app.route('/film/hapus/<int:id>')
def hapus_film(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM film WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    flash('Film telah berhasil dihapus.', 'danger')
    return redirect(url_for('kelola_film'))

# 5. Menjalankan Aplikasi
if __name__ == '__main__':
    app.run(debug=True)