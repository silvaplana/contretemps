# AppBase — Module `trials` (Essai)

Version 0.1 du 18 novembre 2026. Décisions de Seb du 18 novembre 2026. Repris de Sambo Admin
(`silvaplana/test-python`, `backend/src/trials/`, `frontend/src/Trials.jsx`,
`frontend/src/essai/`), à fonctions identiques sauf le certificat médical (§6). Étude :
https://claude.ai/artifact/7HPSBAeGZ5YrE4jahT213a (partie 7 bis). Maquette :
https://claude.ai/artifact/3iTgQGr9aJFFyJTuZZ5kcX ; les écrans la suivent exactement. Rien n'est
codé.

## 1. Ce que fait le module

Une personne qui veut essayer un cours s'inscrit seule, sans compte, sur la page publique de
l'école. Elle reçoit par mail un QR code par personne, qu'elle montre au prof au début du cours.
Le prof le scanne : le cours d'essai est noté. Deux cours d'essai au plus par personne.

Un élève à l'essai n'est pas un membre de l'école : pas de fiche, pas d'invitation, pas de
HelloAsso. Module optionnel, **éteint par défaut** (case « Essais » dans Admin > École >
Personnalisation > Fonctionnalités) : rien ne change pour les écoles qui ne l'allument pas,
Contretemps et Le Beausset compris. Allumé dans les écoles de combat (ASC La Ciotat), comme
HelloAsso et FFST (Seb, 18 novembre). Il ne dépend d'aucun autre module.

## 2. Page publique (sans compte)

Adresse : `https://<école>/essai` (ex. `alliance-sambo-combat-la-ciotat.assofight.silvaplana.cloud/essai`),
aux couleurs et avec le logo de l'école. Page introuvable si le module est éteint.

Bascule (Seb, 18 novembre) : cette page a sa propre adresse et **n'est branchée à rien** au départ.
La page d'essai de Sambo Admin, liée depuis le vrai site du club, reste en service sans qu'on y
touche. Seb changera lui-même le lien sur le site du club quand il le décidera.

Dans l'ordre : nom et logo de l'école ; titre et sous-titre ; texte d'accueil ; **Modalités** (les
lignes des réglages, puis « Les mineurs sont accueillis à partir de N ans et inscrits par un parent
ou représentant légal ») ; **Horaires d'entraînement** ; les salles avec **Voir sur la carte** (lien
Google Maps fait à partir de l'adresse) ; **Inscription** ; **Contact téléphone** ; la mention de
conservation (§6).

Formulaire, comme Sambo Admin :
- de 1 à 3 personnes d'une même famille, **même e-mail** ; « + Ajouter une personne de la même
  famille », « Retirer cette personne » ;
- par personne : Prénom, Nom, « Cette personne est mineure » (alors parent ou représentant légal :
  la 1re personne par défaut, ou « Le parent n'est pas … » avec son prénom et son nom ; Âge, entre
  l'âge minimum et 17 ans), certificat médical obligatoire (photo ou PDF, photos d'iPhone acceptées,
  15 Mo au plus), décharge à cocher (texte des réglages avec le nom de la personne) ;
- l'e-mail sur la 1re personne seulement ;
- **signature au doigt** : la 1re personne si elle est majeure, et chaque parent extérieur (une
  seule signature par nom). Au-dessus de la signature d'un parent, le texte d'autorisation
  parentale : signer vaut autorisation ;
- bouton **Valider l'inscription** ; erreurs en clair (« Merci de joindre le certificat médical de
  … », « Merci de faire signer … »).

Après envoi : **Inscription confirmée**, un QR code par personne avec son nom, « Un e-mail avec le
QR code a été envoyé à … (pensez à regarder dans les courriers indésirables) ». Une personne déjà
inscrite (même prénom, nom et e-mail) n'est pas recréée : « déjà inscrit(e) », même QR code renvoyé.

Garde-fous repris : 10 demandes par heure au plus depuis la même connexion, taille maximale des
fichiers et des signatures.

## 3. Mail de confirmation

Envoyé par l'expéditeur Brevo de l'enseigne, au nom de l'école, réponses vers l'email de contact de
l'école (`core.md`), **copie à l'email de contact de l'école** (§6). Objet « Cours d'essai : <prénom
nom de la 1re personne> ». Contenu : « Votre cours d'essai gratuit », un QR code par personne,
modalités, horaires, les informations renseignées et la version de la décharge acceptée, les
signatures, et **les certificats médicaux en pièces jointes**.

## 4. Admin > Essais

Puce **Essais** d'Admin, entre Adhérents et Profs, visible des administrateurs quand le module est
allumé.

- Titre « Élèves à l'essai (n) », bouton principal **Scanner les QR codes**, menu ⋮ : **Ajouter un
  inscrit à la main** (ouvre le formulaire de la page publique, comme Sambo Admin), **Page d'essai**
  (§5), **Copier le lien de la page d'essai**.
- Recherche (nom, prénom, e-mail, sans majuscules ni accents) ; puces **Pas encore adhérents** (par
  défaut : cache ceux qui ont une fiche d'élève de l'école au même nom et prénom) et **Tous**.
- Colonnes : **Inscrit**, **1er cours**, **2e cours** (date et « QR » ou « à la main »), **Âge**
  (« 12 ans » ou « majeur »), **Inscription** (date, « à la main » si ajouté par un admin),
  **Commentaire**, bouton **+ Cours aujourd'hui** (grisé quand les deux cours sont faits).
- Couleur du nom : vert si le 1er cours est aujourd'hui, orange si un cours est déjà fait, rouge si
  les deux sont faits ; légende sous le tableau. Phrase : « Un inscrit est supprimé tout seul un an
  après son dernier cours ou son inscription. »
- Toucher une ligne ouvre la **fiche** (← revient au tableau) : bouton **Modifier** (prénom, nom,
  âge, e-mail, téléphone, parent, dates des deux cours ; effacer une date retire le cours ;
  Enregistrer / Annuler) ; **Cours d'essai** et « + Cours aujourd'hui » ; **Inscription** (en ligne
  ou à la main, date, âge, parent, e-mail, téléphone, « Même demande que … ») ; **Documents** :
  **Signature et décharge** (signature, version du texte, date ; « vaut autorisation parentale »
  pour un parent), et la phrase « Certificat médical fourni le … Il n'est pas gardé dans l'appli : il
  est joint au mail de confirmation, dont une copie est arrivée sur l'adresse du club. » ;
  **Commentaire** ; **Supprimer …** sans confirmation, avec Annuler pendant 10 s.
- **Scanner les QR codes** (← revient au tableau) : caméra arrière ; chaque résultat s'ajoute en
  haut d'une liste et la caméra continue : « ok pour le cours d'essai 1 aujourd'hui » (vert),
  « … cours d'essai 2 aujourd'hui (dernier) » (orange), « déjà noté aujourd'hui » (vert, rien
  ajouté), « les 2 cours d'essai ont déjà été faits le … et le … » (rouge), « Code inconnu »
  (rouge). Vibration au cours ajouté. Un QR code scanné avec l'appareil photo du téléphone ouvre
  l'appli sur cet écran (adresse `…/?essai=<jeton>`), après connexion si besoin.

## 5. Page d'essai (réglages de l'école)

Admin > Essais > ⋮ > **Page d'essai**. Ce qui était écrit dans le code de Sambo Admin pour ASC
devient un réglage ; pour ASC, les textes de Sambo Admin sont repris tels quels. En haut : le lien
de la page, **Copier le lien**, **Voir la page**. Volets dépliables :
- **Présentation** : titre, sous-titre, texte d'accueil ;
- **Modalités** : une ligne par règle (+ Ajouter une ligne, ✕), **Âge minimum** ;
- **Horaires d'entraînement** : jour, heure, cours, salle ;
- **Salles** : nom et adresse ;
- **Contacts téléphone** : prénom et numéro ;
- **Certificat, décharge et autorisation parentale** : consigne du certificat, texte de la
  décharge, texte de l'autorisation parentale ; [élève], [parent] et [club] sont remplacés par les
  vrais noms.

Bouton principal **Enregistrer**. Changer la décharge ou l'autorisation crée une nouvelle version :
chaque inscription garde la version acceptée (texte compris). Administrateurs de l'école.

## 6. Certificat médical : jamais gardé (Seb, 18 novembre 2026)

Écart voulu avec Sambo Admin, qui garde le certificat un an sur le serveur. Ici le fichier envoyé
sert seulement à faire le mail de confirmation : photo tournée, réduite à 2000 px et mise en JPEG
(PDF tel quel), jointe au mail envoyé à la famille et en copie à l'email de contact de l'école,
puis oubliée. Rien sur le disque, rien en base sauf « certificat fourni le … ». Si le mail ne peut
pas partir (pas d'email de contact, Brevo en panne), l'inscription est refusée avec « Envoi
impossible, réessayez dans un instant » plutôt que de garder le fichier. Pièces jointes au total
limitées à la taille acceptée par Brevo (à vérifier au codage) ; si elle est dépassée, l'inscription
est refusée avec « Certificats trop lourds : envoyez des photos plus petites ».

Mention sur la page publique : « Vos informations servent uniquement à organiser votre cours
d'essai. Elles sont supprimées automatiquement au bout d'un an. Le certificat médical n'est pas
gardé : il est seulement joint au mail de confirmation. Pour les faire supprimer plus tôt, répondez
au mail de confirmation. »

## 7. Données

Tables préfixées `trial_`, toutes filtrées par `organization_id` :
- `trial_settings` : une ligne par école, les textes du §5 (listes en JSON) ;
- `trial_terms` : versions de la décharge et de l'autorisation acceptées (école, numéro, textes,
  date) ;
- `trial_students` : école, prénom, nom, âge ou majeur, e-mail, téléphone, parent,
  commentaire, origine (en ligne / à la main), famille (même demande), jeton du QR code (aléatoire,
  unique), version acceptée, décharge acceptée, date du certificat fourni, adresse de connexion,
  date d'inscription ; dates et mode (QR / à la main) des deux cours ;
- `trial_signatures` : école, famille, nom du signataire, image PNG, date, adresse de connexion.

**Suppression automatique** : chaque nuit, un inscrit sans inscription ni cours depuis un an est
supprimé avec ses signatures (tâche du worker, comme les autres purges).

## 8. Risques

| Risque | Parade |
|---|---|
| Le club n'a plus le certificat s'il perd le mail | copie à l'email de contact de l'école ; c'est le choix de Seb |
| Décharge modifiée par erreur dans les réglages | chaque inscription garde la version et le texte acceptés |
| QR codes déjà envoyés par Sambo Admin | reprise des inscrits avec leur jeton par une commande que Seb lance (`python -m app.reprise_essais`, étape 3) ; le lien de la page publique change sur le site du club |
| Page ouverte à tous : inscriptions fantaisistes, gros fichiers | 10 demandes par heure par connexion, tailles maximales |
| Données de mineurs | rien de santé gardé ; suppression au bout d'un an ; administrateurs seulement |

## 9. Étapes (chacune une PR, sur le « vas-y » de Seb)

1. Module, réglages (§5), page publique, mail, Admin > Essais (tableau, fiche, + Cours
   aujourd'hui), suppression au bout d'un an. **Codée le 18 novembre.** Pas encore : la
   mention « à la main » à l'inscription quand un administrateur ajoute quelqu'un (tout
   s'affiche « en ligne »).
2. Scanner les QR codes (caméra, ouverture par l'appareil photo du téléphone).
3. Reprise des inscrits de Sambo Admin (commande lancée par Seb sur le VPS, Sambo Admin lu en
   copie, sans y toucher).
