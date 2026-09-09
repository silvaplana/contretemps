# api/

Couche d'accès aux données du frontend — un fichier par domaine, symétrique
aux modules du backend (`backend/src/<module>/`). But : que les écrans
n'aient jamais à savoir si l'app tourne en mode démo (données en dur,
`../data/mockData.js`) ou en mode réel (vraie API FastAPI).

## Principe

Chaque fichier `<domaine>.js` expose des fonctions **async**, avec la même
signature qu'elles parlent au mock ou au vrai backend. La bascule se fait
**une seule fois par fonction**, en consultant `mode.js` — jamais dans les
écrans, qui appellent juste `api.xxx.yyy(...)` sans savoir dans quel mode
ils tournent.

Voir `auth.js` comme exemple de référence (`login`/`voirMaquette`).

## Mode démo par défaut

`mode.js` retourne `estModeDemo() === true` par défaut, tant que personne
n'a explicitement basculé en mode réel (pas encore fait au 09/2026 — décision
volontaire : garder l'exemple en dur fiable pendant que le vrai backend se
stabilise). `voirMaquette()` (côté `auth.js`) ignore complètement le mode
courant et retourne toujours la maquette : c'est le filet de sécurité,
disponible même si quelqu'un bascule le mode par erreur ou si l'API réelle
est en panne.

## Étendre à un nouveau domaine (ex. eleves)

1. Créer `eleves.js` avec les fonctions dont les écrans ont besoin (ex.
   `lister(ecoleId)`, `creer(...)`).
2. Dans chacune, une implémentation "maquette" (lit/mute les objets de
   `mockData.js`) et une implémentation "réelle" (`fetch` vers l'API,
   même forme de routes que `backend/src/eleves/receiver.py`).
3. `if (estModeDemo()) return xxxMaquette(...); return xxxReel(...)`.

Pas encore fait pour les autres domaines (eleves, cours, presence...) —
seul `auth.js` existe pour l'instant, les écrans continuent de recevoir
leurs données via les props/état de `App.jsx` (initialisées depuis
`mockData.js`) comme avant. Migrer chaque domaine reste à faire quand on
branchera vraiment le frontend sur le backend.
