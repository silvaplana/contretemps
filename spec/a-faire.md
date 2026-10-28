# Ce qui reste à faire (état au 27 octobre 2026)

Tout ce qui est dans `main` est en ligne. Liste courte ; le détail est dans la spec de chaque
module. Rayer ce qui est fait.

## Sur le « vas-y » de Seb

- Financier : pièces et comptabilité pour les documents de l'AG (`modules/financier.md` §8),
  quatre étapes ; AG de Contretemps en novembre 2026, la première étape suffit à la Synthèse.
- Socle par saison (`core.md` §13) : groupes, droits, cours = groupes, champs des membres, famille
  par l'email du payeur, création de saison en un écran, tarifs, HelloAsso (`modules/helloasso.md`),
  formulaire d'inscription de l'appli (à concevoir).
- Saisons en module optionnel (fil du 24 octobre).
- Signature de documents : retours de Seb après ses tests (`modules/signature-documents.md`).
- `SPEC.md` à réduire à ce qui est propre à Contretemps.

## En cours

- Connexion bancaire du Financier (`modules/financier.md` §3.5) : codée le 28 octobre, à essayer
  avec BoursoBank (école de test) puis le CIC de l'école. Ensuite : lecture automatique, rappel
  avant l'expiration, relevés PDF du CIC.
- Création d'école avec son premier administrateur (prénom, nom, email ; administrateur principal
  et invitation), puis ouverture d'Admin › École pour les premières informations (Seb, 28 octobre).
  Aujourd'hui personne ne peut ajouter le premier administrateur d'une école neuve.

## En attente d'une décision de Seb

- Mot pour « membre + compte de connexion ».
- SMS : prestataire (Brevo proposé). Certificat médical : jamais enregistré.
- Conversations de l'assistant en base (aujourd'hui en mémoire du serveur).

## Rappels pour qui reprend

- Migrations en production : `deploy.sh` les applique ; toujours après une sauvegarde.
- L'assistant ne voit jamais la santé des membres ; il n'écrit jamais un chiffre.
- Tests : `cd backend && pytest` ; les tests de PDF échouent sans Chromium, c'est connu.
