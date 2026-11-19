HelloAsso : pas d'onglet. Pour une école dont les adhésions se font et se paient sur HelloAsso :
l'appli s'y connecte, reprend les champs et les tarifs d'une campagne, et recopie les inscrits. Rien
n'est jamais créé ni changé sur HelloAsso depuis l'appli.

Case : Admin › École › Personnalisation › Fonctionnalités. Connexion : Admin › École › Connexions, ligne HelloAsso
- Seuls l'administrateur principal et le super user cochent la case et voient la connexion.
- Sous le nom : « Pas encore connecté » ou « Connecté à <association> », et un lien « Connecter » ou
  « Voir ».
- Connecter HelloAsso : « Ouvrir mon espace HelloAsso », menu Mon compte › Intégrations et API,
  copier les deux clés dans « Mon clientId » et « Mon clientSecret » (l'œil affiche la clé).
- « Tester la connexion » : « Connexion réussie » avec l'association et le nombre de formulaires, ou
  « La connexion n'a pas marché » et la raison. Puis « Enregistrer ».
- Voir : « Connecté », l'association, depuis quand, le bloc « Saison <nom> » (ce que la saison fait
  de HelloAsso) et le rappel « N'oubliez pas de brancher chaque saison à sa campagne HelloAsso dans
  « Saisons » », les formulaires d'adhésion trouvés ; « Tester la connexion », « Changer les clés »,
  « Déconnecter » (« Annuler » proposé 10 secondes).

Comment chaque saison utilise HelloAsso : Admin › École › Saisons › « Éditer la saison », sous les
dates (administrateur principal et super user, toute saison qu'on édite, HelloAsso connecté), trois choix
qui s'enregistrent tout de suite (« Valider » ne sert qu'au nom et aux dates) :
- « HelloAsso fait tout » : on choisit la campagne HelloAsso dans la carte ; les adhérents viennent
  de HelloAsso (voir plus bas). « Synchroniser maintenant ».
- « L'appli fait tout, HelloAsso encaisse » : inscriptions, champs, tarifs et adhérents dans l'appli ;
  le paiement par carte de l'inscription en ligne arrive sur le compte HelloAsso de l'association.
- « Sans HelloAsso » : rien ne passe par HelloAsso cette saison.
- Quitter « HelloAsso fait tout » retire la campagne, les réponses restent (« Annuler » 10 secondes).
- Le choix vaut pour la saison et se refait à chaque nouvelle saison.

La campagne de la saison : Admin › Élèves › menu ⋮ › Champs (« La fiche d'un membre »)
- En tête, si HelloAsso est connecté : « Nos champs » ou « Imposés par HelloAsso ».
- Imposés par HelloAsso : choisir la « Campagne HelloAsso ». Ses questions passent sur la fiche,
  verrouillées, marquées « Calculé par HelloAsso » ; on peut ajouter nos propres champs à côté.
- Choisir ou changer la campagne : administrateur principal et super user ; les autres admins la
  voient.
- « Synchroniser maintenant » (tout admin) : « Synchronisé : 2 nouvelles fiches, 1 fiche
  complétée ».
- Revenir à « Nos champs » retire la campagne, les réponses restent (« Annuler » 10 secondes).

Tarifs : Admin › École › Tarifs
- Avec une campagne : « Tarifs de la campagne HelloAsso … : ils se modifient sur HelloAsso. »
- Formules (prix, « Dès … » pour un prix libre, en plusieurs fois), Options et codes promo (avec
  « Utilisé n fois »). Tout est en lecture seule, à la place des tarifs de l'appli.

Adhérents imposés par HelloAsso : Admin › Élèves (« Adhérents » si l'école a ce mot), saison dont la
campagne est choisie
- En haut : « Adhérents (n) » (les adhésions résiliées ne comptent pas) et « Rafraîchir » (recopie
  tout de suite depuis HelloAsso ; la saison affichée).
- « Rechercher un adhérent... » (nom, prénom ou email) ; filtres par âge : Tous, Juniors (moins de
  18 ans), Seniors, -10, 10-20, 20-30, 30-40, 40-50, 50+.
- Colonnes par défaut : Adhérent, Email (du payeur), Montant, Code promo, Photo, Statut HelloAsso
  (« Validé HelloAsso » ou « Résilié »). Les autres colonnes s'affichent par « Affichage dans Admin ».
- Toucher la photo l'agrandit. Menu ⋮ : « Masquer les photos » / « Afficher les photos » (sur cet
  appareil), Champs.
- Une adhésion résiliée reste dans le tableau, grisée, nom barré.
- Pas de « + », ni d'import, ni de poubelle : on ajoute quelqu'un sur HelloAsso (paiement en
  espèces ou par chèque compris), il arrive par la synchronisation. Le serveur refuse aussi.
- La fiche (toucher le nom) : photo, Adhésion (formule, montant, code promo, statut HelloAsso),
  Documents déposés sur HelloAsso (photo d'identité, certificat médical… : ouverts depuis HelloAsso,
  jamais gardés), Réponses au formulaire (« Modifiable sur HelloAsso. »), Payeur, Paiements.
- Revenir à « Nos champs » ou éteindre le module rend le tableau habituel.

Contacter ou résilier un adhérent : Admin › Élèves, saison imposée par HelloAsso
- Colonne Contact : « ✉ Mail » (le nombre déjà envoyé à côté) ouvre « Mail à … » : choisir un
  message préenregistré ou écrire Objet et Message, puis Envoyer. Le mail part à l'email du payeur,
  l'école est en copie et reçoit les réponses.
- « 💬 SMS » (sur téléphone seulement, quand HelloAsso a donné un numéro) : écrire ou choisir le
  message puis « Ouvrir mes SMS » ; le SMS part de l'appli SMS du téléphone.
- « Garder ce message » enregistre le texte comme message préenregistré ; {prénom} et {nom} sont
  remplacés ; « Retirer ce message préenregistré » l'enlève.
- Colonne Adhésion : « Résilier » (droit Accès au Financier) montre toute la commande HelloAsso
  (une fratrie entière est résiliée ensemble), ce qui est déjà encaissé et ne sera pas remboursé,
  les échéances annulées. Définitif. Le remboursement se fait dans l'espace HelloAsso du club.
- Dans la fiche : rubrique Messages envoyés.

Vérifier les dossiers des adhérents (saison imposée par HelloAsso)
- À allumer d'abord : Admin › Personnalisation › Fonctionnalités › HelloAsso › Voir, bloc
  « Nouveaux adhérents » (Administrateur principal) : « Prévenir les administrateurs à chaque nouvel
  adhérent » et « Vérifier le dossier de chaque adhérent ». Éteints au départ.
- Colonne Vérification d'Admin › Élèves : « OK » ou « À vérifier ». « À vérifier » montre les raisons
  et les documents ; « Écrire à l'adhérent » ouvre le mail ; « Valider le dossier » le compte OK
  (Annuler pendant 10 s).
- La fiche a aussi une rubrique « Vérification du dossier » avec « Valider le dossier ».
- Menu ⋮ › « Vérifier les adhérents » (Accès au Financier) : relance la vérification de tous les
  dossiers pas encore OK ; le rapport arrive par mail à l'adresse de l'école ; le coût cumulé est
  affiché.
- Un nouvel adhérent est vérifié tout seul ; s'il y a un problème, l'école reçoit un mail.
- Les documents sont lus sur HelloAsso pour la vérification, jamais gardés.

Statistiques de la saison (saison imposée par HelloAsso)
- Admin › Élèves, menu ⋮ › « Statistiques des adhérents de la saison » (tout admin) : majeurs,
  mineurs, prix moyen ; encaissements des adhésions (déjà arrivé sur le compte courant, reste à
  encaisser), dépliables ; bouton Fermer.
- Avec l'Accès au Financier : solde actuel de chaque compte et « Solde projeté » à la fin de la
  saison (solde + reste à encaisser − salaires et cotisations − licences FFST encore à payer).
- Les chiffres viennent de HelloAsso et des comptes du Financier ; rien n'est modifiable ici.

À encaisser : Admin › À encaisser (sous-onglet après Cours, module allumé, tout admin ; pastille rouge =
  nombre d'échéances dépassées sans paiement)
- En haut « À encaisser », « Rafraîchir » (recopie depuis HelloAsso puis relit) et le chiffre « Doit
  encore arriver sur le compte » (partie 1 + partie 2).
- « 1. À payer à HelloAsso » : les échéances que les adhérents doivent encore payer (date, nom,
  « Paiement 2 »…, somme). Dépassée sans paiement = en rouge, en tête, avec le nombre et le total ;
  les autres par mois. « Aucune échéance à payer. »
- « 2. HelloAsso doit verser au compte » : « Virement en route » et « Gardé par HelloAsso » (versé
  vers le 10 du mois suivant).
- Sans campagne pour la saison : « Pas de campagne HelloAsso pour cette saison. »

Où voir les paiements
- Saison imposée par HelloAsso : dans la fiche de l'adhérent, rubrique Paiements. Sinon, sur
  HelloAsso.
- L'argent versé par HelloAsso sur le compte de l'école : Financier › Pièces › Ventes.
- Paiement par carte de la page d'inscription en ligne : il passe aussi par HelloAsso (voir les
  inscriptions en ligne).

Règles de l'appli
- Les inscrits sont recopiés toutes les 5 minutes pour la saison en cours, ou par « Synchroniser
  maintenant ». Une saison passée n'est recopiée que par « Synchroniser maintenant » (l'écran le dit :
  « Saison passée : pas de recopie automatique… »).
- Une commande retrouve sa fiche par nom et prénom, sinon par email du payeur et prénom ; sinon une
  fiche d'élève est créée. Une adhésion résiliée, annulée ou remboursée est recopiée quand même,
  avec son état (« Résilié »).
- Quelqu'un retiré sur HelloAsso garde sa fiche dans l'appli.
- Déconnecter ne touche ni aux membres ni aux paiements déjà recopiés.
- Les clés sont gardées chiffrées.
