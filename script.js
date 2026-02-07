document.addEventListener('DOMContentLoaded', () => {
    const feed = document.getElementById('feed');
    const DATA_URL = 'data/events.json';
    const MONTHS = {'01':'Janvier','02':'Février','03':'Mars','04':'Avril','05':'Mai','06':'Juin','07':'Juillet','08':'Août','09':'Septembre','10':'Octobre','11':'Novembre','12':'Décembre'};

    function getDateFromId(id) {
        const match = id.match(/[A-Z]+(\d{6})/i);
        if (match && match[1]) {
            const dateStr = match[1];
            const yy = parseInt(dateStr.substring(0, 2), 10);
            const mm = dateStr.substring(2, 4);
            const dd = dateStr.substring(4, 6);
            const fullYear = (yy >= 80) ? 1900 + yy : 2000 + yy;
            return `${parseInt(dd)} ${MONTHS[mm] || 'Inconnu'} ${fullYear}`;
        }
        return 'Date Inconnue';
    }

    function cleanTitle(title) {
        return title.replace(/\s*\(.*?\)$/, '').trim();
    }

    function getTypeInfo(typeString) {
        const t = (typeString || '').toLowerCase();
        if (t.includes('bbh')) return { class: 'bbh', label: 'TR. NOIRS' };
        if (t.includes('bns')) return { class: 'bns', label: 'NEUTRONS' };
        if (t.includes('nsbh')) return { class: 'mix', label: 'MIXTE' };
        return { class: 'def', label: 'COMPACT' };
    }

    fetch(DATA_URL)
        .then(response => {
            if (!response.ok) throw new Error("Erreur chargement JSON");
            return response.json();
        })
        .then(data => {
            feed.innerHTML = ''; 

            data.forEach(event => {
                const realDate = getDateFromId(event.id);
                const cleanTitleText = cleanTitle(event.title);
                const typeInfo = getTypeInfo(event.type);
                const badgeColorVar = `var(--color-${typeInfo.class})`;
                
                // Si la distance n'est pas dans le JSON (vieux cache), on met 'N/A'
                const distanceText = event.distance || "N/A";

                const article = document.createElement('article');
                article.className = 'card';
                article.innerHTML = `
                    <div class="card-header">
                        <span class="badge" style="background-color: ${badgeColorVar}">
                            ${typeInfo.label}
                        </span>
                        <span class="date">${realDate}</span>
                    </div>

                    <h2>${cleanTitleText}</h2>
                    <p class="summary">${event.summary}</p>

                    <div class="card-footer">
                        <div class="meta-group">
                            <span class="meta-label">ID ÉVÉNEMENT</span>
                            <a href="${event.url}" target="_blank" class="id-link">
                                <span class="meta-value">${event.id}</span> ↗
                            </a>
                        </div>
                        <div class="meta-group right-align">
                            <span class="meta-label">DISTANCE</span>
                            <span class="meta-value distance-value">${distanceText}</span>
                        </div>
                    </div>
                `;
                feed.appendChild(article);
            });
        })
        .catch(err => {
            feed.innerHTML = `<div class="loader" style="color:red">Erreur: ${err.message}</div>`;
        });
});
