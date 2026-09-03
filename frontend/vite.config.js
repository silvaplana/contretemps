import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  // En build (utilisé par le Dockerfile de prod), l'app est servie sous
  // /contretemps/ sur silvaplana.cloud : le Caddy "gateway" partagé du VPS
  // route ce chemin vers ce conteneur (voir ~/gateway sur le VPS, et
  // DEPLOY.md). Sans ce "base", les fichiers JS/CSS générés seraient
  // référencés depuis la racine du domaine et ne seraient pas trouvés.
  // En dev local (`npm run dev`), on reste à la racine pour plus de simplicité.
  base: command === 'build' ? '/contretemps/' : '/',
  plugins: [react()],
}))
