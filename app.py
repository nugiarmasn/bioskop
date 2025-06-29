from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_untuk_flash_message'

# Konfigurasi koneksi ke Database Anda
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '', # Sesuaikan jika password MySQL Anda berbeda
    'database': 'bioskop' # Nama database yang Anda gunakan
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# Pemetaan nilai kualitatif ke kuantitatif untuk SAW
GENRE_SCORES = {'Aksi': 4, 'Komedi': 5, 'Horor': 3, 'Sci-Fi': 4, 'Animasi': 5, 'Drama': 3}
UMUR_SCORES = {'SU': 5, '13+': 4, '17+': 3}

@app.route('/', methods=['GET', 'POST'])
def index():
    hasil = None
    langkah_perhitungan = None
    bobot_sebelumnya = {}

    if request.method == 'POST':
        try:
            bobot = {
                'w1': float(request.form['w1']), 'w2': float(request.form['w2']),
                'w3': float(request.form['w3']), 'w4': float(request.form['w4']),
                'w5': float(request.form['w5']),
            }
            bobot_sebelumnya = bobot.copy()
            
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM film")
                alternatif_list = cursor.fetchall()
                conn.close()

                if not alternatif_list:
                    flash('Tidak ada data film di database untuk dihitung.', 'warning')
                    return redirect(url_for('index'))

                # --- PROSES PERHITUNGAN SAW ---
                matriks_keputusan = []
                for alt in alternatif_list:
                    matriks_keputusan.append({
                        'id': alt['id'], 'judul': alt['judul'], 'genre': alt['genre'], 'kesesuaian_umur': alt['kesesuaian_umur'],
                        'harga_tiket': alt['harga_tiket'], 'review_penonton': float(alt['review_penonton']),
                        'skor_cuplikan': alt['skor_cuplikan'], 'nilai_genre': GENRE_SCORES.get(alt['genre'], 0),
                        'nilai_umur': UMUR_SCORES.get(alt['kesesuaian_umur'], 0)
                    })
                langkah_perhitungan = {'matriks_keputusan': matriks_keputusan}
                
                min_c1 = min(d['harga_tiket'] for d in matriks_keputusan)
                max_c2 = max(d['review_penonton'] for d in matriks_keputusan)
                max_c3 = max(d['skor_cuplikan'] for d in matriks_keputusan)
                max_c4 = max(d['nilai_genre'] for d in matriks_keputusan) if any(d['nilai_genre'] > 0 for d in matriks_keputusan) else 1
                max_c5 = max(d['nilai_umur'] for d in matriks_keputusan) if any(d['nilai_umur'] > 0 for d in matriks_keputusan) else 1
                
                matriks_normalisasi = []
                for data in matriks_keputusan:
                    norm_c1 = min_c1 / data['harga_tiket'] if data['harga_tiket'] != 0 else 0
                    norm_c2 = data['review_penonton'] / max_c2 if max_c2 != 0 else 0
                    norm_c3 = data['skor_cuplikan'] / max_c3 if max_c3 != 0 else 0
                    norm_c4 = data['nilai_genre'] / max_c4 if max_c4 != 0 else 0
                    norm_c5 = data['nilai_umur'] / max_c5 if max_c5 != 0 else 0
                    matriks_normalisasi.append({'id': data['id'], 'judul': data['judul'], 'c1': norm_c1, 'c2': norm_c2, 'c3': norm_c3, 'c4': norm_c4, 'c5': norm_c5})
                langkah_perhitungan['matriks_normalisasi'] = matriks_normalisasi

                hasil_akhir = []
                for data in matriks_normalisasi:
                    skor = (bobot['w1'] * data['c1'] + bobot['w2'] * data['c2'] + bobot['w3'] * data['c3'] + bobot['w4'] * data['c4'] + bobot['w5'] * data['c5'])
                    hasil_akhir.append({'id': data['id'], 'judul': data['judul'], 'skor': skor, 'normalisasi': data})
                hasil = sorted(hasil_akhir, key=lambda x: x['skor'], reverse=True)
        except Exception as e:
            flash(f'Terjadi error saat perhitungan: {e}', 'danger')

    return render_template('index.html', hasil=hasil, langkah=langkah_perhitungan, bobot_sebelumnya=bobot_sebelumnya)

@app.route('/film')
def kelola_film():
    films = []
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM film ORDER BY id DESC")
        films = cursor.fetchall()
        conn.close()
    return render_template('kelola_film.html', films=films)

@app.route('/film/tambah', methods=['GET', 'POST'])
def tambah_film():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                query = "INSERT INTO film (judul, genre, kesesuaian_umur, harga_tiket, review_penonton, skor_cuplikan) VALUES (%s, %s, %s, %s, %s, %s)"
                data = (request.form['judul'], request.form['genre'], request.form['kesesuaian_umur'], request.form['harga_tiket'], request.form['review_penonton'], request.form['skor_cuplikan'])
                cursor.execute(query, data)
                conn.commit()
                conn.close()
                flash('Film baru berhasil ditambahkan!', 'success')
                return redirect(url_for('kelola_film'))
        except Exception as e:
            flash(f'Gagal menambahkan film: {e}', 'danger')
    return render_template('form_film.html', title='Tambah Film Baru', film=None)

@app.route('/film/edit/<int:id>', methods=['GET', 'POST'])
def edit_film(id):
    conn = get_db_connection()
    if not conn:
        flash('Koneksi database gagal.', 'danger')
        return redirect(url_for('kelola_film'))
        
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        try:
            query = "UPDATE film SET judul=%s, genre=%s, kesesuaian_umur=%s, harga_tiket=%s, review_penonton=%s, skor_cuplikan=%s WHERE id=%s"
            data = (request.form['judul'], request.form['genre'], request.form['kesesuaian_umur'], request.form['harga_tiket'], request.form['review_penonton'], request.form['skor_cuplikan'], id)
            cursor.execute(query, data)
            conn.commit()
            flash('Data film berhasil diperbarui!', 'info')
        except Exception as e:
            flash(f'Gagal mengedit film: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('kelola_film'))
        
    cursor.execute("SELECT * FROM film WHERE id = %s", (id,))
    film = cursor.fetchone()
    conn.close()
    return render_template('form_film.html', title='Edit Data Film', film=film)

@app.route('/film/hapus/<int:id>')
def hapus_film(id):
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM film WHERE id = %s", (id,))
            conn.commit()
            conn.close()
            flash('Film telah berhasil dihapus.', 'danger')
    except Exception as e:
        flash(f'Gagal menghapus film: {e}', 'danger')
    return redirect(url_for('kelola_film'))

if __name__ == '__main__':
    app.run(debug=True)