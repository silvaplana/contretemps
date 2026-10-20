# Ce qui reste à faire (état au 16 octobre 2026)

Tout ce qui est dans `main` est en production (code, migrations jusqu'à
`d4b6f8a0c2e1`, bloc Caddy des pages en ligne). Liste tenue à jour à la fin
de chaque session ; rayer ou retirer ce qui est fait.

## À essayer par Seb en production (jamais essayé en vrai)

- Page en ligne d'un fichier : passer un fichier en Officiel, puis Diffuser >
  Tout le monde (le certificat se crée à la première visite, quelques secondes).
- Envoi par email aux personnes choisies, avec le lien personnel.
- Une vraie demande de modification à l'assistant (carte récapitulative
  « Tout faire / Annuler ») : essayée seulement avec un faux Claude.
- OnlyOffice : l'aperçu suit-il bien après une modification ?

## Prêt à faire

- Relances par email aux non-répondants (`doc_sends` sans `answered_at`) ; fait pour la convocation d'AG (procurations.md §10),
  même lien (voir `passation-fichier-de-base.md` §3).
- Garder les conversations de l'assistant en base (aujourd'hui en mémoire du
  serveur, perdues à chaque redémarrage ou mise en ligne).
- « Demander à l'assistant » dans le menu d'un fichier de Docs : sur
  téléphone, l'assistant est en plein écran, on ne peut plus y glisser un
  fichier de la liste.

## En attente d'une décision de Seb

- SMS : choix d'un prestataire (Brevo proposé, même compte que les emails).
- Fichier de base : date limite, notification dans l'appli, visibilité des
  réponses, adresses externes (`fichier-de-base.md` §2.3).
- Certificat médical : jamais enregistré.
- Page d'inscription publique : prend « la première école ».
- Formulaire de création d'école.
- Étape Android de la connexion par mot de passe (reportée).
- Tarifs (questions du 2 octobre) : 31,60 € ou 31,67 € ; réduction de 5 € en
  septembre.

## Ménage (quand Seb le voudra)

- Sauvegardes `/app/data/avant_*.db` sur le serveur (6, la plus récente :
  `avant_fichier_de_base_2026-10-16.db`) : à supprimer après validation.
- Branches GitHub jamais fusionnées : `claude/spec-plusieurs-emails`,
  `spec/logo-avif`, `spec/mot-de-passe-invitation`.

## Rappels pour qui reprend

- Migrations en production : à la main (`docker compose exec backend alembic
  upgrade head`), toujours après une sauvegarde et avec l'accord de Seb.
- L'assistant ne voit jamais la santé des élèves ; le commentaire de
  l'administration et le rouge d'Admin > Élèves : admins et Super User
  seulement.
- Valider des définitions d'outils Claude sans frais : `messages.count_tokens`.
