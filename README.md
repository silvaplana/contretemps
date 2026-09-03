# Contretemps

Application (smartphone uniquement pour l'instant) de gestion d'école de
danse et de ses activités.

Le passage en appli native iOS/Android est prévu plus tard, via
[Capacitor](https://capacitorjs.com/) qui emballe le build React existant
sans le réécrire — d'ici là, le frontend reste une app web mobile-first
classique (pas de PWA, pas de dépendance à des API navigateur qui
casseraient dans une WebView).

## Structure

```
contretemps/
├── backend/     # API REST FastAPI (voir backend/README.md)
└── frontend/    # Application React, mobile-first (voir frontend/README.md)
```

## Backend

Voir [backend/README.md](backend/README.md) pour l'installation,
l'utilisation et les tests.

## Frontend

Voir [frontend/README.md](frontend/README.md).

## Déploiement

Pas encore mis en place. Suivra le pattern de
[test-python](../test-python) (backend + frontend/Caddy dockerisés,
docker-compose, VPS) une fois qu'il y aura quelque chose à déployer.
