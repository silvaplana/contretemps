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
set -euo pipefail

script="$(readlink -f "$0")"
cd "$(dirname "$script")"

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
