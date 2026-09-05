# frontend

Application React (Vite), pensée mobile-first : conçue pour un écran de
smartphone, pas pour être élargie en layout desktop (voir `index.css`).

## Installation

```bash
npm install
```

Copier `.env.example` en `.env` (`VITE_API_URL` doit pointer vers le
backend, `http://localhost:8000` par défaut).

## Utilisation

```bash
npm run dev
```

Autres scripts : `npm run build`, `npm run lint` (oxlint), `npm run preview`.

## Appli Android

Voir [ANDROID.md](../ANDROID.md) à la racine du repo — le projet Android
(Capacitor) est dans `android/`, généré à partir de ce frontend.
`npm run build:android` fait le build web adapté (racine `/`, sortie dans
`dist-android/`), différent de `npm run build` (chemin `/contretemps/`,
utilisé pour le déploiement web).
