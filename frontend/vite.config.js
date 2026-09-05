import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => ({
  // En build web (utilisé par le Dockerfile de prod), l'app est servie sous
  // /contretemps/ sur silvaplana.cloud : le Caddy "gateway" partagé du VPS
  // route ce chemin vers ce conteneur (voir ~/gateway sur le VPS, et
  // DEPLOY.md). Sans ce "base", les fichiers JS/CSS générés seraient
  // référencés depuis la racine du domaine et ne seraient pas trouvés.
  // En dev local (`npm run dev`), on reste à la racine pour plus de simplicité.
  // En build Capacitor (`npm run build:android`, voir ANDROID.md), l'app
  // tourne dans une WebView locale sans préfixe de chemin : la racine "/"
  // est donc obligatoire, pas "/contretemps/".
  base: command === 'build' && mode !== 'capacitor' ? '/contretemps/' : '/',
  build: {
    // Dossier séparé pour ne jamais mélanger le build web (base
    // /contretemps/, servi par Docker/Caddy) et le build Capacitor (base /,
    // embarqué dans l'appli Android) : voir capacitor.config.json.
    outDir: mode === 'capacitor' ? 'dist-android' : 'dist',
  },
  plugins: [react()],
}))
