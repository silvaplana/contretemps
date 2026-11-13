#!/usr/bin/env bash
# Déploiement sur le VPS (voir DEPLOY.md §3 et §5) : les mêmes commandes
# que la mise à jour à la main, en une seule fois.
#
# Lancé de deux façons :
#   - par GitHub Actions (.github/workflows/deploy.yml), à chaque fusion
#     dans main : la clé de déploiement est limitée, dans
#     ~/.ssh/authorized_keys, à lancer ce script et rien d'autre ;
#   - à la main sur le VPS : ./deploy.sh
#
# Le script se met d'abord à jour lui-même (git pull), puis se relance pour
# que ce soit toujours la dernière version qui fasse le reste.
#
# Maintenance (DEPLOY.md §6) : l'action GitHub « Maintenance » demande une
# tâche par la connexion SSH ; elle arrive dans SSH_ORIGINAL_COMMAND (la
# clé ne peut lancer que ce script). Seules les tâches de la liste
# ci-dessous existent ; tout le reste est refusé. Rien n'est jamais évalué.
set -euo pipefail

script="$(readlink -f "$0")"
cd "$(dirname "$script")"

if [ -n "${SSH_ORIGINAL_COMMAND:-}" ]; then
  read -r -a demande <<< "$SSH_ORIGINAL_COMMAND"
  tache="${demande[0]:-}"
  case "$tache" in
    notes-frais-lister)
      echo "==> Notes de frais par école (rien n'est effacé)"
      docker compose exec -T backend python -m app.vider_notes_frais --lister
      ;;
    notes-frais-vider)
      ecole="${demande[1]:-}"
      if ! [[ "$ecole" =~ ^[0-9]+$ ]]; then
        echo "Numéro d'école invalide : rien n'a été effacé." >&2
        exit 2
      fi
      # Nom en base64 : il peut contenir des espaces et des accents.
      if ! nom="$(printf '%s' "${demande[2]:-}" | base64 -d 2>/dev/null)"; then
        echo "Nom illisible : rien n'a été effacé." >&2
        exit 2
      fi
      echo "==> Effacement des notes de frais de l'école $ecole"
      docker compose exec -T backend python -m app.vider_notes_frais --ecole "$ecole" --nom "$nom"
      ;;
    plan-comptable-contretemps)
      # Comptes de la Balance 24-25 de la trésorière (spec financier.md §8.2) ;
      # « essai » en 3e mot : affiche sans écrire.
      ecole="${demande[1]:-}"
      if ! [[ "$ecole" =~ ^[0-9]+$ ]]; then
        echo "Numéro d'école invalide : rien n'a été fait." >&2
        exit 2
      fi
      if [ "${demande[2]:-}" = "essai" ]; then
        echo "==> Plan comptable de Contretemps pour l'école $ecole (essai à blanc)"
        docker compose exec -T backend python -m app.plan_comptable_contretemps --ecole "$ecole" --essai
      else
        echo "==> Plan comptable de Contretemps pour l'école $ecole"
        docker compose exec -T backend python -m app.plan_comptable_contretemps --ecole "$ecole"
      fi
      ;;
    labo-lire)
      # Fights › Labo (Seb, 12/11/2026) : ce que le serveur a vu dans un
      # essai, en lecture seule ; sans numéro, la liste des essais.
      essai="${demande[1]:-}"
      if [ -z "$essai" ]; then
        echo "==> Essais du Labo (rien n'est écrit)"
        docker compose exec -T backend python -m app.lire_essai_labo
        # Les dernières lignes du lecteur de vidéos de Fights : l'erreur
        # d'une lecture échouée (« Vidéo illisible »).
        echo "==> Journal du lecteur de Fights"
        docker compose logs --no-color --tail=80 sparring-worker
      elif [[ "$essai" =~ ^[0-9]+$ ]]; then
        echo "==> Essai $essai du Labo (rien n'est écrit)"
        docker compose exec -T backend python -m app.lire_essai_labo --essai "$essai"
      else
        echo "Numéro d'essai invalide." >&2
        exit 2
      fi
      ;;
    seance-lire)
      # Fights › Tournage (Seb, 13/11/2026) : ce que le serveur a vu dans une
      # séance de la caméra, en lecture seule ; sans numéro, les 10 dernières.
      seance="${demande[1]:-}"
      if [ -z "$seance" ]; then
        echo "==> Dernières séances de Fights (rien n'est écrit)"
        docker compose exec -T backend python -m app.lire_seance_fights
        echo "==> Journal du lecteur de Fights"
        docker compose logs --no-color --tail=80 sparring-worker
      elif [[ "$seance" =~ ^[0-9]+$ ]]; then
        echo "==> Séance $seance de Fights (rien n'est écrit)"
        docker compose exec -T backend python -m app.lire_seance_fights --seance "$seance"
      else
        echo "Numéro de séance invalide." >&2
        exit 2
      fi
      ;;
    *)
      echo "Tâche inconnue : « $tache ». Tâches possibles : notes-frais-lister, notes-frais-vider, plan-comptable-contretemps, labo-lire, seance-lire." >&2
      exit 2
      ;;
  esac
  exit 0
fi

if [ -z "${DEPLOY_APRES_PULL:-}" ]; then
  echo "==> git pull"
  git pull --ff-only
  DEPLOY_APRES_PULL=1 exec "$script" "$@"
fi

echo "==> Version : $(git log -1 --format='%h %s')"

echo "==> Reconstruction et redémarrage des conteneurs"
docker compose up -d --build

echo "==> Attente du backend"
pret=""
for _ in $(seq 1 30); do
  if docker compose exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" \
    >/dev/null 2>&1; then
    pret=1
    break
  fi
  sleep 2
done
if [ -z "$pret" ]; then
  echo "Le backend ne répond pas après 60 s. Derniers journaux :"
  docker compose logs --tail=50 backend
  exit 1
fi

echo "==> Migrations de la base (alembic upgrade head)"
docker compose exec -T backend alembic upgrade head

echo "==> Ménage des anciennes images"
docker image prune -f >/dev/null

echo "==> Déploiement terminé"
docker compose ps
