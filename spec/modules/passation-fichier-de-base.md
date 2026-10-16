# Passation : fichier de base et assistant (état au 16 octobre 2026)

Pour reprendre le travail en local avec Claude Code. Tout ce qui est décrit ici
est dans `main` (PR #6, fusionnée le 16 octobre, commit `de38f4a`).

À lire d'abord, dans cet ordre :
1. ce fichier ;
2. `spec/modules/fichier-de-base.md` (la spec du fichier de base, avec ce qui
   est codé noté au fil du texte, et les décisions de Seb en §4 et §7) ;
3. `spec/modules/documents.md` et `spec/modules/documents-phase-contretemps.md`
   (le module documents dans son ensemble, et le plan par étapes).

## 1. Ce qui est fait

**Fichier de l'appli** (nouvelle sorte de nœud `app` dans le module documents) :
- + > Créer un fichier : on choisit la nature (Informer, Questionner, Agir) ; le
  fichier s'ouvre en plein écran avec les onglets Préparer | Aperçu | Diffuser |
  Résultats, qui suivent l'état (Brouillon, Validé, Officiel).
- Contenu : JSON de blocs façon BlockNote, `{schema, entry:{blocks}, result:{blocks}}`,
  contrôlé par `backend/src/documents/app_content.py` (jamais de HTML ; blocs
  permis selon la nature). Versions dans `doc_app_versions` (fusion des
  enregistrements d'une même personne sur 10 min, conflit 409).
- Réponses dans `doc_responses` (une table pour tous les fichiers, valeurs par id
  de question ; `is_test` pour les essais ; `source` = test / public / link).
- Faire un modèle (admins) : `doc_app_templates`, tuiles « de l'école » dans le +.
- Diffuser :
  - « Tout le monde » (Officiel seulement) : page en ligne
    `https://<page>.<école>.contretemps.silvaplana.cloud` (`doc_publications`,
    nom de page jamais réutilisé), QR code, réponses sans compte ;
  - « Des personnes choisies » : un email par personne avec lien personnel
    `<adresse de l'école>/r/<jeton>` (`doc_sends`), une réponse par lien qu'on
    corrige en revenant, suivi envoyé / ouvert / répondu / échec. En Validé, la
    carte devient « Faire relire » : personnes une par une (10 au plus),
    réponses d'essai, lien fermé au passage en Officiel (décision de Seb).

**Assistant** (`backend/src/assistant/`, écran `frontend/src/modules/documents/`) :
- Un seul chat pour toute l'appli : bouton dans l'en-tête à droite du badge du
  profil, même conversation dans tous les onglets, ouvert/fermé gardé sur
  l'appareil (`AssistantGlobal.jsx`, état dans `assistantGlobal.js`). Dans Docs,
  l'explorateur s'y branche (`brancherDocs`) pour donner le dossier ouvert et
  faire les cartes ; ailleurs, le contexte envoyé est `{onglet}`.
- Chaque fichier de l'appli a son propre chat, qui part de zéro (bulle dans
  Préparer, `AppFile.jsx`) ; il écrit les formulaires avec l'outil
  `modifier_fichier_appli` (`assistant/fichier_appli.py`), avec « Annuler ».
- Outils ajoutés : `proposer_creer_fichier_appli` (carte Faire / Annuler) ;
  `proposer_modifications` accepte `commentaire_admin`, `ligne_rouge`,
  `cellules_rouges` (admins et Super User ; jamais la santé).
- Les conversations vivent en mémoire du serveur (perdues au redémarrage).

**Élèves en rouge** : le surlignage d'Admin > Élèves (appui long) est en base
(`profils_eleves.ligne_rouge`, `cellules_rouges`), plus seulement à l'écran.

## 2. Mise en production (à faire par Seb, Claude n'a pas accès au VPS)

1. `git pull`, puis côté backend `alembic upgrade head` : deux migrations,
   `c7e9a1b3d5f2` (tables du fichier de base) et `d4b6f8a0c2e1` (rouge des élèves).
2. Caddy : ajouter le bloc `*.*.contretemps.silvaplana.cloud` décrit dans
   `DEPLOY.md` (section « Pages en ligne des fichiers »), sinon les pages en
   ligne ne s'ouvrent pas.
3. Les emails de Diffuser partent par le SMTP déjà configuré (`SMTP_*`).
   Réponses au mail : à l'adresse de la personne qui envoie (l'école n'a pas
   encore d'adresse de contact).

## 3. Ce qui reste

- **3c, SMS et relances** : SMS en attente du choix d'un prestataire par Seb
  (Brevo proposé, même compte que les emails). Les relances par email peuvent
  se faire tout de suite : renvoyer aux non-répondants (`doc_sends` sans
  `answered_at`), même lien. Aussi : date limite, notification de l'appli,
  visibilité des réponses, adresses externes (spec §2.3).
- Garder les conversations du chat en base.
- « Ce qui change à chaque fois » quand on touche une tuile de modèle (spec §5).
- Bloc Image dans BlockNote (reporté).
- Sous-agents (un agent par fichier qui parle à l'assistant général) : repoussé
  au kit AG (étape 6 du plan).

## 4. Travailler en local

- Backend : `cd backend && pip install -e .` ; tests `python3 -m pytest`.
  Tests du travail ci-dessus : `tests/test_documents_app.py`,
  `tests/test_assistant.py`, `tests/test_assistant_modifications.py`,
  `tests/test_eleves.py`, `tests/test_personnalisation.py`.
- **24 tests échouent aussi sur main** : ils viennent du PDF Chromium dans
  l'environnement de test, pas du fichier de base.
- Frontend : `cd frontend && npm run dev` (Vite, port 5173), `npx oxlint src`.
- Mails sans SMTP en développement : `MAILS_DANS_LES_JOURNAUX=1`, le mail est
  écrit dans les journaux du serveur.
- Page en ligne en développement : `http://<page>.<école>.localhost:5173`
  (l'école de démo est `contretemps-83330`) ; lien personnel :
  `http://contretemps-83330.localhost:5173/r/<jeton>`.
- Le module documents reste isolé (identifiants anglais, ports dans
  `documents/ports.py`) ; tout ce qui est propre à Contretemps passe par
  `documents_contretemps/adapter.py` (annuaire, saisons, envoi des mails).
- Routes publiques (sans compte) : à déclarer dans `comptes/rbac.py`
  (`ROUTES_PUBLIQUES`).

## 5. Règles de Seb à garder

- Français, mots du métier, jamais « IA » ni concept technique à l'écran ; un
  bouton principal par écran ; « Gros et simple » (texte ≥ 17 px, touches ≥ 48 px).
- Dire « nature », pas « type ». Familles : Informer ⓘ sarcelle, Questionner ?
  violet, Agir ⚡ orange.
- L'assistant propose, la personne fait (cartes Faire / Annuler) ; il n'écrit
  jamais un chiffre inventé ; jamais les données de santé.
- Chaque étape = une PR que Seb relit et met en ligne lui-même.
- Tenir la spec à jour dans `spec/modules/` quand une décision change.
