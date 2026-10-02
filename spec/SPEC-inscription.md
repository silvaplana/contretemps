# Spécification — Parcours inscription à l'ecole de danse contretemps

Ceci est la specification du parcours d'inscription d'un utilisateur pour une saison a l'ecole de danse contretemps.
C'est une specification différente de l'appli "Contretemps" de gestion de l'école de danse contretemps (spec.md).
En effet, ce parcours d'inscription n'est pas destiné à être primordialement inclus dans l'appli "Contretemps", mais surtout être atteignable à partir de la page web du site https://www.dansecontretemps.fr/cours-danse-Beausset.

Donc on spécifie ici la page web https://silvaplana.cloud/contretemps-inscription , qui est differente de l'application https://silvaplana.cloud/contretemps/.

## 1. Contraintes:
La page d'inscription doit pouvoir etre atteignable depuis le site de l'ecole contretemps https://www.dansecontretemps.fr (priorité) , ou l'appli contretemeps https://silvaplana.cloud/contretemps/
Cette inscription ecrira et communiquera  avec la base de donnée de l'application contretemps . 


## 2. Description du parcours d'inscription:
Voici le parcours d'inscription que doit permettre de realiser cette page:

* remplissage par l'adherent du formule qui est actuellement le fichier pdf https://3a80cb6a-cec5-4d2f-bac2-064c29a539f5.filesusr.com/ugd/6115fc_bc985868014c40908180e4483e4fcae4.pdf

* Verification de  l'inscription par rapport a la feuille excel '//wsl.localhost/Ubuntu-26.04/home/srichard/DEV/contretemps/data/Adhérents 2025 2026 MAJ 20 mars Test.xlsx'
Question: faut il faire la verification apres chaque champ, ou une fois l'inscription des champs effectuée.

* calcul du tarif a payer et indication du prix dans le formulaire https://www.dansecontretemps.fr/cours-danse-beausset 

* choix par l'utilisateur du moyen de paiement, en 1 fois ou 3 fois. 3 moyens de paiement possible:
- par cheque: dans ce cas il n'y a rien à faire
- par l'api stripe 
- par l'api hello asso

* Envoi d'un mail par l'adresse mail sebastien.richard54@gmail.com (sera plus tard remplacé par un mail d'un administrateur contretemps) à l'utilisateur, contenant en pièce jointe son dossier d'inscription rempli, et une facture de ce qu'il a payé

* Envoi d'un 2e mail, séparé, à l'administrateur cette fois (voir Remarque ci-dessous) : "Inscription de <Prénom Nom> en base des inscrits", avec le fichier Excel "nouvelles inscriptions" en pièce jointe.


* inscription de l'utilisateur dans la feuille excel '//wsl.localhost/Ubuntu-26.04/home/srichard/DEV/contretemps/data/Adhérents 2025 2026 MAJ 20 mars Test.xlsx'

// ne pas prendre en compte, commentaire
//* inscription dans la base de donnée de l'élève dans la base de donnée contretemps.  Dans l'application contretemps, le front end effectue déjà sur le backend contretemps une //inscription par Rest: peut etre peut on utliser le meme canal.



## Remarque — 3 trimestres par an, jamais en été

Le montant "trimestriel" (voir `montant_trimestriel`, barème page tarifs du dossier papier)
correspond à 3 échéances par an — il n'y a jamais de trimestre facturé pendant l'été (juillet/
août, l'école étant fermée). Toujours afficher "3 échéances"/"3 trimestres", jamais 4.

## Remarque — mois de septembre hors scope

Le parcours d'inscription décrit ici ne traite PAS la spécificité du mois de septembre (le vrai
dossier d'inscription papier distingue un tarif "mois de septembre" du tarif mensuel/trimestriel
classique — voir la colonne `montant_mensuel_septembre` côté backend). Le montant calculé et
affiché ici est celui du barème tel quel, sans logique métier supplémentaire propre à septembre
(proratisation, échéance différente, etc.) : si un jour l'école a besoin d'un traitement
spécifique pour septembre, ce sera une évolution séparée, pas couverte par cette spec.

## Remarque — deux emails distincts après chaque inscription

Une inscription finalisée (voir `inscriptions.py:_finaliser`, déclenché après choix du chèque, ou
paiement carte confirmé) envoie 2 emails **séparés**, chacun dans son propre `try`/`except` :
un échec de l'un ne doit jamais empêcher l'autre, ni l'inverse.

1. **À la famille** (voir `_envoyer_email`) : confirmation, dossier + facture en pièces jointes —
   décrit ci-dessus.
2. **À l'administrateur** (voir `_notifier_admin`), décision utilisateur explicite :
   - Objet : `Inscription de <Prénom Nom> en base des inscrits`.
   - Corps : `<Prénom Nom> a été ajouté(e) aux nouveaux inscrits. Vous pouvez copier sa ligne du
     fichier Excel en pièce jointe dans votre Excel officiel. Vous pourrez ensuite réintégrer
     votre Excel officiel dans l'application Contretemps. Votre excel officiel fait foi.`
   - Pièce jointe : le même fichier Excel "nouvelles inscriptions" que
     `GET /inscriptions/export` (Admin > École > "Télécharger les nouvelles inscriptions"),
     à jour de la ligne qui vient d'être ajoutée — l'admin n'a pas besoin de se reconnecter à
     l'appli pour le récupérer.
   - Destinataire : variable d'env `ADMIN_EMAIL` — si absente, part vers `SMTP_USER` (l'expéditeur)
     par défaut, pour fonctionner sans configuration supplémentaire tant que l'admin et
     l'expéditeur sont la même personne (voir `.env.example`).

## 3. Ordre des développements:

Coder d'abord tout le parcours décrit ci-dessus, dans l'ordre chronologique, sauf le paiement stripe ou hello asso.
Points techniques

Ensuite coder le paiement hello asso. D'abord dans la sand box hello asso , puis dans un vrai hello asso si c'est possible (peut on le créer?)
Ensuite coder le paiement stripe

## 4. Paiement HelloAsso — décisions et fonctionnement (voir inscriptions/helloasso.py)

**Sandbox d'abord** : l'association Contretemps n'a pas encore de compte HelloAsso réel. On code
et teste entièrement contre un compte de test créé sur
https://auth.helloasso-sandbox.com/inscription (association fictive, indépendante de la vraie
identité de l'école — n'importe quel compte sandbox convient pour tester). Un vrai compte
HelloAsso sera créé plus tard pour Contretemps ; basculer en prod ne demandera de changer que 4
variables d'environnement (`HELLOASSO_API_BASE`, `HELLOASSO_CLIENT_ID`, `HELLOASSO_CLIENT_SECRET`,
`HELLOASSO_ORGANIZATION_SLUG`), aucune ligne de code.

**API utilisée** : Checkout Intent API (dev.helloasso.com) — on crée une "intention de paiement"
côté serveur (montant, infos payeur), HelloAsso renvoie une `redirectUrl` vers laquelle le
navigateur est redirigé ; la famille paie sur la page HelloAsso, puis revient sur notre
`returnUrl`.

**1 fois ou 3 fois** (décision utilisateur) : la famille choisit. En 3 fois, la 1ʳᵉ échéance
regroupe adhésion + 1er trimestre (payée immédiatement), puis une échéance par trimestre suivant
espacée d'1 mois (voir `tarifs.py:calculer_echeances_helloasso` — respecte les contraintes de
l'API : max 1 échéance/mois, jamais après le 27 du mois, jamais dans le mois de l'échéance
initiale, toujours dans les 12 mois).

**Vérification du paiement** : la signature webhook HMAC (`x-ha-signature`) est réservée aux
comptes HelloAsso "partenaire" — pas notre cas pour une association normale. On ne fait donc
JAMAIS confiance au simple retour navigateur ni au corps d'une notification webhook : on
ré-interroge systématiquement l'API (`GET .../checkout-intents/{id}`, source de vérité) avant de
marquer une inscription "payée" — au retour de paiement (`returnUrl`) ET si un webhook est
configuré plus tard (redondant par construction, l'un fonctionne même si l'autre est absent).

**Hors scope de cette 1ère passe** : le paiement Stripe (viendra après, une fois HelloAsso validé
en sandbox puis en prod — voir §3 ci-dessus).
## 5. Inscription à partir d'une fiche papier (« Ajouter élève (OCR) ») — décisions du 2026-10-02

Pour les familles qui rendent la fiche d'inscription papier, remplie à la main.

- **Entrée** : Admin > Élèves, menu ⋮, « Ajouter élève (OCR) ». Réservé aux admins.
- **Photos** : la fiche est en recto verso, il faut 2 photos (recto : élève, cours, urgence, santé ; verso : droit à l'image et règlement). Pour chaque face : « Importer fichier » (image ou PDF, par l'explorateur de fichiers), « Galerie » (photos du téléphone) ou « Prendre photo ». Le verso est facultatif.
- **Lecture** : le serveur envoie les photos à l'API Claude (`ANTHROPIC_API_KEY`, voir `inscriptions/lecture_fiche.py`), qui renvoie les champs du formulaire en ligne, la liste des champs dont la lecture est incertaine, et une remarque éventuelle. Les cours sont déduits des disciplines et du niveau cochés, parmi les cours de l'école.
- **Coût** : affiché dès la fin de la lecture, puis dans le formulaire et sur l'écran de confirmation (en dollars, tel que facturé).
- **Correction** : le formulaire d'inscription en ligne s'ouvre pré-rempli (`/contretemps-inscription/?fiche=<jeton>`). C'est le MÊME formulaire : aucun écran en double. Les champs incertains sont surlignés jusqu'à ce que l'admin y touche ; les photos de la fiche sont consultables sur la page.
- **Enregistrer l'élève ou annuler** (décision du 2026-10-02, remplace le passage par le paiement) : en bas du formulaire, deux boutons, « Enregistrer l'élève » et « Annuler ». Pas d'étape de paiement. « Annuler » efface le brouillon et ses photos.
- **Enregistrer l'élève** ajoute l'élève DIRECTEMENT à la liste officielle (Admin > Élèves), pas aux inscriptions en attente : nom, prénom, date de naissance, adresse, téléphone, email, cours suivis, un contact (la personne à prévenir), santé, montant de l'année calculé d'après les cours. Le droit à l'image et le règlement, sans colonne dédiée, vont dans le commentaire (« Fiche papier du JJ/MM/AAAA. Droit à l'image : oui (site internet). Règlement signé par … »). Si un élève du même nom existe déjà, l'appli prévient et demande de confirmer.
- **Mail** à l'administrateur (`ADMIN_EMAIL`), titre « Inscription papier validée de <prénom> <nom> à l'école <école> pour la saison <saison> », avec en pièces jointes le dossier d'inscription rempli (le même PDF que pour une inscription en ligne) et les photos de la fiche. Aucun mail à la famille. Les photos sont ensuite effacées du serveur.
- **Email facultatif** dans ce parcours ; la case du règlement est pré-cochée si la fiche est signée.
- **Brouillon** : gardé 24 heures au plus, dans le dossier privé de l'école, accessible par un jeton tiré au hasard. Pas de table.
- **Données personnelles** : la fiche (données d'un enfant, dont santé) est envoyée à Anthropic pour lecture. À mentionner dans le règlement ou sur la fiche.
- **Droit à l'image** : une case cochée (site, réseaux, affiches) vaut autorisation, même si la mention « J'autorise / Je n'autorise pas » n'est pas rayée.
- **Espèces** (2026-10-02) : troisième moyen de paiement du formulaire en ligne, sous « Chèque », avec les mêmes échéances (1 ou 3 fois) ; remis à l'école, l'inscription est finalisée tout de suite comme pour un chèque.
- **Mail de l'inscription en ligne** (2026-10-02) : titre « Inscription en ligne validée de <prénom> <nom> à l'école <école> pour la saison <saison> », envoyé à l'email de l'élève, avec l'administrateur en copie.
- **Enchaînement des fiches** (2026-10-02) : le formulaire pré-rempli s'affiche dans l'appli (dans un cadre), pas dans un autre onglet. Après « Enregistrer l'élève », pas d'écran de fin : retour à l'écran de saisie OCR, vide, pour la fiche suivante, avec un message temporaire en bas « <prénom> <nom> a été ajouté(e) aux adhérents <saison> ». La liste d'Admin > Élèves est relue aussitôt.
