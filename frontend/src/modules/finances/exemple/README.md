# Écrans d'exemple « Pièces et comptabilité »

Écrans de `spec/modules/financier.md` §8 montrés tels quels dans l'appli, avec les chiffres de
2024-25 (`donnees.js`), avant de coder l'étape 1. Rien n'est enregistré sur le serveur.

- `Pieces.jsx` : sous-onglet Pièces (dossiers, photo en rafale, rattachement).
- `Virements.jsx` : puce Virements de Pièces (§8.3 bis : quatre états, aide au virement).
- `FicheOperation.jsx` : fiche d'une ligne de Comptes (compte, pièce, écritures).
- `PlanComptable.jsx` : Comptes ⋯ › Plan comptable (et réglage Simple / Complet), Soldes de départ.
- `Caisse.jsx` : puce Caisse de Comptes.
- `DocumentsAG.jsx` : bloc Documents de l'AG sous un bilan, Synthèse à l'écran.
- `BandeExemple.jsx`, `exemple.css` (tout sous `.fin-ex`).

Branchements dans l'appli (à garder quand le réel arrive) : `Financier.jsx` (sous-onglet, menu ⋯),
`Comptes.jsx` (puce Caisse, compte et pièce sur chaque ligne, appui sur une ligne, volets),
`Bilan.jsx` (bloc sous le résultat). Le dossier entier disparaît avec l'étape 1.
