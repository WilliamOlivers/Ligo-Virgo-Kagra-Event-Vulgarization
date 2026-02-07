document.addEventListener('DOMContentLoaded', () => {
    const feed = document.getElementById('feed');
    const DATA_URL = 'data/events.json'; // Assure-toi que le chemin est bon

    // Dictionnaire des mois pour la traduction
    const MONTHS = {
        '01': 'Janvier', '02': 'Février', '03': 'Mars', '04': 'Avril',
        '05': 'Mai', '06': 'Juin', '07': 'Juillet', '08': 'Août',
        '09': 'Septembre', '10': 'Octobre', '11': 'Novembre', '12': 'Décembre'
    };

    /**
     * Extrait la date lisible depuis l'ID GraceDB (ex: S251117dq -> 17 Novembre 2025)
     * C'est notre filet de sécurité si le JSON contient "Date inconnue"
     */
    function getDateFromId(id) {
        // Regex pour capturer les 6 chiffres après S, MS, ou GW
        const match = id.match(/[A-Z]+(\d{6})/i);
        if (match && match[1]) {
            const dateStr = match[1]; // ex: 251117
            const yy = parseInt(dateStr.substring(0, 2), 10);
            const mm = dateStr.substring(2, 4);
            const dd = dateStr.substring(4, 6);

            // Gestion 1900/2000
            const fullYear = (yy >= 80) ? 1900 + yy : 2000 + yy;
            const monthName = MONTHS[mm] || 'Inconnu';

            return `${parseInt(dd)} ${monthName} ${fullYear}`;
        }
        return 'Date Inconnue';
    }

    /**
     * Nettoie le titre généré par l'IA pour enlever les mentions de date erronées
     * Ex: "Fusion (Date Indéterminée)" -> "Fusion"
     */
    function cleanTitle(title) {
        return title.replace(/\s*\(.*?\)$/, '').trim();
    }

    /**
     * Détermine la classe CSS et le libellé court selon le type
     */
    function getTypeInfo(typeString) {
        const t = typeString.toLowerCase();
        if (t.includes('bbh') || t.includes('trous noirs')) {
            return { class: 'bbh', label: 'BLACK HOLES' };
        }
        if (t.includes('bns') || t.includes('neutrons')) {
            return { class: 'bns', label: 'NEUTRON STARS' };
        }
        if (t.includes('nsbh')) {
            return { class: 'mix', label: 'MIXTE' };
        }
        return { class: 'def', label: 'COMPACT' };
    }

    /**
     * Génère les points visuels pour le score (Scientific Score)
     */
    function generateScoreDots(score) {
        let html = '<div class="score-dots" title="Intérêt scientifique: ' + score + '/10">';
        for (let i = 1; i <= 10; i++) {
            html += `<span class="dot ${i <= score ? 'active' : ''}"></span>`;
        }
        html += '</div>';
        return html;
    }

    // Chargement des données
    fetch(DATA_URL)
        .then(response => {
            if (!response.ok) throw new Error("Impossible de charger le fichier JSON");
            return response.json();
        })
        .then(data => {
            feed.innerHTML = ''; // Effacer le loader

            data.forEach(event => {
                // 1. Calcul de la vraie date via JS (plus fiable que le JSON actuel)
                const realDate = getDateFromId(event.id);
                
                // 2. Nettoyage du titre
                const cleanTitleText = cleanTitle(event.title);

                // 3. Infos de badge
                const typeInfo = getTypeInfo(event.type);

                // 4. Style CSS dynamique pour le badge
                const badgeColorVar = `var(--color-${typeInfo.class})`;

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
                            <a href="${event.url}" target="_blank" style="color:inherit; text-decoration:none;">
                                <span class="meta-value">${event.id}</span> ↗
                            </a>
                        </div>
                        <div class="meta-group">
                            <span class="meta-label">RARETÉ /10</span>
                            ${generateScoreDots(event.score)}
                        </div>
                    </div>
                `;
                feed.appendChild(article);
            });
        })
        .catch(err => {
            feed.innerHTML = `<div class="loader" style="color:red">Erreur : ${err.message}</div>`;
            console.error(err);
        });
});
