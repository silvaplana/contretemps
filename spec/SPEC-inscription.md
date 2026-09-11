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