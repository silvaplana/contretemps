# Contretemps

Application (smartphone uniquement pour l'instant) de gestion d'école de
danse et de ses activités.

Le frontend reste une app web mobile-first classique (pas de PWA, pas de
dépendance à des API navigateur qui casseraient dans une WebView). Le
passage en appli native se fait via [Capacitor](https://capacitorjs.com/),
qui emballe le build React existant sans le réécrire — voir
[ANDROID.md](ANDROID.md) pour le projet Android (déjà généré dans
`frontend/android/`) ; iOS suivra le même principe plus tard.

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

Le projet est "dockerisé" (backend + frontend/nginx) et rejoint le
gateway partagé du VPS `silvaplana.cloud` (même serveur que
`test-python` et `fight-rank`). Voir [DEPLOY.md](DEPLOY.md).
