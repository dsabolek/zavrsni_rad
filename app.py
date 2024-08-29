import os
import uuid
from flask import Flask, request, redirect, url_for, render_template, session, flash, jsonify
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from google.cloud import vision, storage, firestore

# Postavi varijablu okruženja za pristup Firestore-u
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "zavrsnirad-key.json"

# Inicijalizacija Flask aplikacije
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Inicijalizacija Google Cloud klijenata
db = firestore.Client()
storage_client = storage.Client()
vision_client = vision.ImageAnnotatorClient()

# Funkcija za provjeru dopuštenih ekstenzija datoteka
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# Ruta za registraciju korisnika
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Kriptiranje lozinke prije spremanja u bazu podataka
        hashed_password = generate_password_hash(password)

        # Provjera postoji li već korisnik s istim emailom
        user_ref = db.collection('users').where('email', '==', email).limit(1)
        user_docs = user_ref.stream()

        if len(list(user_docs)) > 0:
            flash('Email je već registriran. Molimo prijavite se.')
            return redirect(url_for('login'))

        # Stvaranje novog korisnika u Firestore-u
        user_data = {
            'email': email,
            'password': hashed_password
        }
        db.collection('users').add(user_data)

        flash('Registracija uspješna, molimo prijavite se')
        return redirect(url_for('login'))

    return render_template('register.html')

# Ruta za prijavu korisnika
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Provjera korisničkih podataka
        user_ref = db.collection('users').where('email', '==', email).limit(1)
        user_docs = user_ref.stream()

        user_doc = None
        for doc in user_docs:
            user_doc = doc.to_dict()
            break

        if user_doc is None:
            flash('Korisnik nije pronađen. Molimo registrirajte se.')
            return redirect(url_for('register'))

        stored_password = user_doc.get('password')

        # Provjera ispravnosti lozinke koristeći check_password_hash
        if not check_password_hash(stored_password, password):
            flash('Neispravan email ili lozinka')
            return redirect(url_for('login'))

        session['user'] = email
        return redirect(url_for('upload_page'))

    return render_template('login.html')

# Ruta za prikaz stranice za učitavanje slike
@app.route('/upload_page')
def upload_page():
    if 'user' not in session:
        flash('Morate se prvo prijaviti')
        return redirect(url_for('login'))

    email = session['user']
    images_ref = db.collection('images').where('email', '==', email)
    images = []
    for doc in images_ref.stream():  # Iterate over the stream
        img = doc.to_dict()
        images.append(img)

    return render_template('upload.html', images=images)

# Funkcija za učitavanje slike u Cloud Storage
def upload_to_bucket(file, filename):
    bucket_name = 'pic_xample'
    bucket = storage_client.bucket(bucket_name)

    blob_name = f'uploads/{uuid.uuid4()}.{filename.rsplit(".", 1)[1].lower()}'
    blob = bucket.blob(blob_name)

    blob.upload_from_file(file)

    # Vraćanje javnog URL-a za blob
    public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

    return public_url

@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return jsonify({'error': 'Morate se prijaviti prvo.'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'Nema dijela datoteke.'}), 400

    file_request = request.files['file']

    if file_request.filename == '':
        return jsonify({'error': 'Nije odabrana datoteka.'}), 400

    if file_request and allowed_file(file_request.filename):
        filename = secure_filename(file_request.filename)
        public_url = upload_to_bucket(file_request, filename)

        # Priprema zahtjeva za Google Cloud Vision API
        image = vision.Image()
        image.source.image_uri = public_url

        response = vision_client.label_detection(image=image)
        labels = response.label_annotations
        
        # Log za sve oznake
        print("Oznake iz Google Cloud Vision API-ja:")
        for label in labels:
            print(f"Labela: {label.description}, Povjerenje: {label.score}")

        possible_breeds = []
        dog_detected = False

        # Prikupljanje oznaka s dovoljno visokim povjerenjem
        for label in labels:
            if 'dog' in label.description.lower() and label.score >= 0.80:
                dog_detected = True
                possible_breeds.append(label.description)

        # Provjerite je li slika prikazuje psa
        if not dog_detected:
            return jsonify({'error': 'To nije pas, molimo unesite sliku psa.'})

        breed_info = None

        if possible_breeds:
            for breed_name in possible_breeds:
                # Koristi The Dog API za dobivanje informacija o pasmini
                api_url = f'https://api.thedogapi.com/v1/breeds/search?q={breed_name}'
                headers = {'x-api-key': 'live_PchmdGac1vmVg7iCzOzj91mJD6J4nYNIXZswBnfE0GSvvisUvBbjwKCDqPTVfOQi'}
                response = requests.get(api_url, headers=headers)
                
                # Log za odgovor The Dog API-ja
                print(f"Odgovor iz The Dog API-ja za {breed_name}: {response.text}")
                
                dog_data = response.json()

                if dog_data and isinstance(dog_data, list) and len(dog_data) > 0:
                    # Odaberi pasminu sa najvišim povjerenjem
                    breed_info = dog_data[0]
                    for breed in dog_data:
                        if breed.get('name').lower() == breed_name.lower():
                            breed_info = breed
                            break
                    if breed_info:
                        break

        if not breed_info:
            breed_info = 'N/A'

        # Spremanje slike u bazu podataka Firestore
        image_data = {
            'email': session['user'],
            'public_url': public_url,
            'breed_info': breed_info,
            'upload_date': firestore.SERVER_TIMESTAMP
        }
        db.collection('images').add(image_data)

        return jsonify({'public_url': public_url, 'breed_info': breed_info})
    return jsonify({'error': 'Neispravan tip datoteke.'}), 400

@app.route('/user_images', methods=['GET'])
def user_images():
    if 'user' not in session:
        return jsonify({'error': 'Morate se prijaviti prvo.'}), 403

    email = session['user']
    images_ref = db.collection('images').where('email', '==', email)

    image_list = []
    for doc in images_ref.stream():  # Iterate over the stream
        img = doc.to_dict()
        image_list.append(img)

    return jsonify(image_list)

# Ruta za odjavu korisnika
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
