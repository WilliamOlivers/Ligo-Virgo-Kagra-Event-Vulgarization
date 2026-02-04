document.addEventListener('DOMContentLoaded', () => {
    const feed = document.getElementById('feed');

    fetch('data/events.json')
        .then(response => {
            if (!response.ok) throw new Error("Fichier de données introuvable");
            return response.json();
        })
        .then(data => {
            feed.innerHTML = ''; // Effacer le loading
            
            data.forEach(event => {
                const dateObj = new Date(event.date);
                const dateStr = dateObj.toLocaleDateString('fr-FR', {
                    year: 'numeric', month: 'long', day: 'numeric'
                });

                const card = document.createElement('article');
                card.className = 'event-card';
                
                card.innerHTML = `
                    <div class="meta">
                        <span class="badge ${event.type}">${event.type}</span>
                        <span>${event.readable_date}</span>
                    </div>
                    <h2>${event.title}</h2>
                    <p class="summary">${event.summary}</p>
                    
                    <div class="details-grid">
                        <div class="detail-item">
                            <span class="label">ID Catalogue</span>
                            <span class="value">${event.id}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Intérêt Sc.</span>
                            <span class="value">${event.score}/10</span>
                        </div>
                    </div>
                    
                    <a href="https://gracedb.ligo.org/superevents/${event.id}/view/" target="_blank" class="raw-link">Source GraceDB &rarr;</a>
                `;
                
                feed.appendChild(card);
            });
        })
        .catch(error => {
            feed.innerHTML = `<p>Erreur de chargement: ${error.message}. <br>Le script Python a peut-être besoin de s'exécuter une première fois.</p>`;
        });
});
