# api/

Couche d'accès aux données du frontend — un fichier par domaine, symétrique
aux modules du backend (`backend/src/<module>/`). Chaque fichier
`<domaine>.js` expose des fonctions **async** appelées par les écrans
(`fetch` vers l'API FastAPI, même forme de routes que
`backend/src/<domaine>/receiver.py`), qui traduisent au passage les noms de
champs (`snake_case` backend <-> `camelCase` écran).

Le mode maquette (données en dur, bascule `mode.js`) qui existait pendant
que le backend se construisait a été entièrement retiré (voir
spec/SPEC.md §8) — tous les domaines parlent désormais uniquement au
vrai backend.
