import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Adresses d'école (spec §2.7) : le nom de l'appli et sa couleur, que
// l'iPhone lit à l'installation AVANT que l'appli ne démarre, sont ceux de
// l'école. Le build les remplace par un appel que Caddy exécute à chaque
// envoi de index.html (voir Caddyfile.ecoles : `templates`). Seulement si
// VITE_ENTETE_ECOLE=1 : le build de l'adresse générique et le dev gardent
// les valeurs de Contretemps.
function enteteEcole() {
  return {
    name: 'entete-ecole',
    transformIndexHtml(html) {
      if (process.env.VITE_ENTETE_ECOLE !== '1') return html
      const debut = html.indexOf('<!-- entete-ecole -->')
      const fin = html.indexOf('<!-- /entete-ecole -->')
      if (debut < 0 || fin < 0) throw new Error('Repères <!-- entete-ecole --> absents de index.html')
      return (
        html.slice(0, debut) +
        '{{httpInclude "/api/par-host/entete.html"}}' +
        html.slice(fin + '<!-- /entete-ecole -->'.length)
      )
    },
  }
}

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
  //
  // Adresses d'école (https://<adresse>.contretemps.silvaplana.cloud, spec
  // §2.7) : l'app y est à la racine, d'où VITE_BASE=/ (voir Dockerfile).
  base: process.env.VITE_BASE ?? (command === 'build' && mode !== 'capacitor' ? '/contretemps/' : '/'),
  build: {
    // Dossier séparé pour ne jamais mélanger le build web (base
    // /contretemps/, servi par Docker/Caddy) et le build Capacitor (base /,
    // embarqué dans l'appli Android) : voir capacitor.config.json.
    outDir: mode === 'capacitor' ? 'dist-android' : 'dist',
  },
  plugins: [react(), enteteEcole()],
}))
