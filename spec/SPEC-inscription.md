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