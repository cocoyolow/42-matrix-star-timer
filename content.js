const TARGET_LOGIN = "opernod";
const API_URL = `http://127.0.0.1:5000/logtime/${TARGET_LOGIN}`;

console.log("🚀 Extension 42 Matrix Overlay chargée");

let userStats = null;

// 1. Récupération des données
fetch(API_URL)
    .then(r => r.json())
    .then(data => {
        userStats = data;
        startPainting();
    })
    .catch(err => console.error("Erreur connexion python:", err));

function startPainting() {
    if (userStats) paintData();
    setInterval(() => {
        if (userStats) paintData();
    }, 2000);
}

function paintData() {
    // On cherche tous les textes
    const elements = document.querySelectorAll('div, text, span, g');

    elements.forEach(el => {
        const text = el.textContent ? el.textContent.trim() : "";
        
        if (userStats[text]) {
            // Si on a déjà traité ce poste, on ne fait rien
            if (el.getAttribute('data-logtime-done')) return;

            const time = userStats[text];

            // STRATÉGIE "OVERLAY" : On se base sur le parent (la case du PC)
            // Le parent direct du texte est souvent la "boite" du poste
            const container = el;
            
            if (container) {
                // On s'assure que le conteneur peut servir de référence
                // (Ne casse pas la layout, permet juste le positionnement absolu des enfants)
                const currentPosition = window.getComputedStyle(container).position;
                if (currentPosition === 'static') {
                    container.style.position = 'relative';
                }

                // Création du badge
                const badge = document.createElement('div');
                badge.textContent = time;
                
                // --- STYLE "OVERLAY" (Au dessus de tout) ---
                badge.style.position = "absolute";
                
                // Centrage parfait au milieu de la case
                badge.style.top = "50%";
                badge.style.left = "50%";
                badge.style.transform = "translate(-50%, -50%)";
                
                // Apparence
                badge.style.backgroundColor = "rgba(0, 186, 188, 0.9)"; // Cyan 42 avec transparence légère
                badge.style.color = "white";
                badge.style.fontSize = "11px";
                badge.style.fontWeight = "bold";
                badge.style.padding = "2px 6px";
                badge.style.borderRadius = "10px"; // Bords bien ronds
                badge.style.boxShadow = "0 0 5px rgba(0,0,0,0.5)"; // Ombre pour lisibilité
                badge.style.zIndex = "1000"; // Passe au dessus des étoiles
                badge.style.pointerEvents = "none"; // On peut cliquer au travers (sur le poste)
                badge.style.whiteSpace = "nowrap";

                // Ajout du badge
                container.appendChild(badge);
                
                // On marque l'élément texte comme traité pour ne pas le refaire
                el.setAttribute('data-logtime-done', 'true');
            }
        }
    });
}
