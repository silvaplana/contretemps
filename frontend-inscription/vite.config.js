import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  // En build (utilisé par le Dockerfile de prod), l'app est servie sous
  // /contretemps-inscription/ sur silvaplana.cloud (voir le Caddy
  // "gateway" partagé du VPS, hors de ce repo, et DEPLOY.md) — sans ce
  // "base", les fichiers JS/CSS générés ne seraient pas trouvés. En dev
  // local (`npm run dev`), on reste à la racine pour plus de simplicité.
  base: command === 'build' ? '/contretemps-inscription/' : '/',
  plugins: [react()],
}))
