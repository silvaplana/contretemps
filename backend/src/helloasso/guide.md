HelloAsso : pas d'onglet. Pour une école dont les adhésions se font et se paient sur HelloAsso :
l'appli s'y connecte, reprend les champs et les tarifs d'une campagne, et recopie les inscrits. Rien
n'est jamais créé ni changé sur HelloAsso depuis l'appli.

Réglages : Admin › École › Personnalisation › Fonctionnalités, ligne HelloAsso
- Seuls l'administrateur principal et le super user cochent la case et voient les réglages.
- Sous le nom : « Pas encore connecté » ou « Connecté à <association> », et un lien « Connecter » ou
  « Voir ». Cocher la case sans connexion ouvre tout de suite l'écran des clés.
- Connecter HelloAsso : « Ouvrir mon espace HelloAsso », menu Mon compte › Intégrations et API,
  copier les deux clés dans « Mon clientId » et « Mon clientSecret » (l'œil affiche la clé).
- « Tester la connexion » : « Connexion réussie » avec l'association et le nombre de formulaires, ou
  « La connexion n'a pas marché » et la raison. Puis « Enregistrer ».
- Voir : « Connecté », l'association, depuis quand, les formulaires d'adhésion trouvés ; « Tester la
  connexion », « Changer les clés », « Déconnecter » (« Annuler » proposé 10 secondes).

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

Où voir les paiements
- Les paiements des inscrits sont recopiés, mais aucun écran ne les montre encore : on les voit sur
  HelloAsso.
- L'argent versé par HelloAsso sur le compte de l'école : Financier › Pièces › Ventes.
- Paiement par carte de la page d'inscription en ligne : il passe aussi par HelloAsso (voir les
  inscriptions en ligne).

Règles de l'appli
- Les inscrits sont recopiés toutes les 5 minutes pour la saison en cours, ou par « Synchroniser
  maintenant ».
- Une commande retrouve sa fiche par nom et prénom, sinon par email du payeur et prénom ; sinon une
  fiche d'élève est créée. Une commande annulée ou remboursée est ignorée.
- Quelqu'un retiré sur HelloAsso garde sa fiche dans l'appli.
- Déconnecter ne touche ni aux membres ni aux paiements déjà recopiés.
- Les clés sont gardées chiffrées.
