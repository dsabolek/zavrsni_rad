document.addEventListener('DOMContentLoaded', function() {
    // Provjera prijavljenog korisnika
    if (document.getElementById('uploadBtn')) {
        loadImages();
    }
});

// Učitavanje slika za prijavljenog korisnika
function loadImages() {
    fetch('/user_images')
        .then(response => response.json())
        .then(data => {
            const imagesDiv = document.getElementById('images');
            imagesDiv.innerHTML = '';
            data.forEach(image => {
                const img = document.createElement('img');
                img.src = `/static/uploads/${image.filename}`;
                img.style.width = '100px';
                imagesDiv.appendChild(img);
                imagesDiv.appendChild(document.createElement('br'));
                imagesDiv.appendChild(document.createTextNode(`Breed: ${image.breed_info}`));
                imagesDiv.appendChild(document.createElement('br'));
                imagesDiv.appendChild(document.createTextNode(new Date(image.upload_date).toLocaleString()));
                imagesDiv.appendChild(document.createElement('br'));
            });
        })
        .catch(error => console.error('Error loading images:', error));
}

// Prijenos slike
document.getElementById('uploadBtn').addEventListener('click', function(event) {
    event.preventDefault();
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    if (file) {
        const formData = new FormData();
        formData.append('file', file);
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            alert(`Breed info: ${data.breed_info}`);
            loadImages();
        })
        .catch(error => console.error('Error uploading image:', error));
    } else {
        alert('Please select a file.');
    }
});
