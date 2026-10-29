# Écrans d'exemple « Pièces et comptabilité »

Écrans de `spec/modules/financier.md` §8 montrés tels quels dans l'appli, avec les chiffres de
2024-25 (`donnees.js`), avant de coder l'étape 1. Rien n'est enregistré sur le serveur.

- `Pieces.jsx` : puces À rattacher et Ventes de Pièces (proposition de la ligne de banque). Notes de
  frais, Honoraires, Achats et Virements sont réels depuis le 29 octobre (`notes-frais/Pieces.jsx`).
- `FicheOperation.jsx` : fiche d'une ligne de Comptes (compte, pièce, écritures).
- `PlanComptable.jsx` : Comptes ⋯ › Plan comptable (et réglage Simple / Complet), Soldes de départ.
- `Caisse.jsx` : puce Caisse de Comptes.
- `DocumentsAG.jsx` : bloc Documents de l'AG sous un bilan, Synthèse à l'écran.
- `BandeExemple.jsx`, `exemple.css` (tout sous `.fin-ex`).

Branchements dans l'appli (à garder quand le réel arrive) : `notes-frais/Pieces.jsx` (puces), `Financier.jsx` (menu ⋯),
`Comptes.jsx` (puce Caisse, compte et pièce sur chaque ligne, appui sur une ligne, volets),
`Bilan.jsx` (bloc sous le résultat). Le dossier entier disparaît avec l'étape 1.
