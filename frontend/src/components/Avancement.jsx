// L'avancement d'une vidéo, du module Vidéos (Seb, 23/11 : « une brique
// vidéo sympa », le même partout) : jaune pendant l'envoi, rayée avec un
// rond qui tourne quand l'envoi n'avance plus (« Attend le réseau »), bleue
// pendant la préparation au serveur, verte quand c'est prêt.
// Chorégraphies se sert de la barre seule ; Fights du bandeau en bas de
// l'écran (Timer et Combats).

export function pourcentEnvoi(progression) {
  return progression?.octetsTotal ? Math.round((100 * progression.octetsEnvoyes) / progression.octetsTotal) : 0
}

// Le texte d'un envoi en cours, d'après useProgressionTeleversement/useProgressionVideo.
export function texteEnvoi(progression) {
  return progression?.bloque ? 'Attend le réseau' : `Envoi ${pourcentEnvoi(progression)} %`
}

// « encore 1 min » : le temps qui reste à la préparation, d'après le serveur.
export function texteReste(secondes) {
  if (secondes == null) return null
  if (secondes < 60) return 'encore quelques secondes'
  return `encore ${Math.round(secondes / 60)} min`
}

export function Tourne() {
  return <i className="avancement-tourne" aria-hidden="true" />
}

// `etape` : 'envoi' | 'preparation' | 'pret'.
export function BarreAvancement({ pourcent, etape = 'envoi', bloque = false, className = '' }) {
  const classes = ['avancement-barre', `avancement-barre--${etape}`]
  if (bloque) classes.push('avancement-barre--bloque')
  if (className) classes.push(className)
  return (
    <i className={classes.join(' ')}>
      <i style={{ width: `${etape === 'pret' ? 100 : Math.max(0, Math.min(100, pourcent ?? 0))}%` }} />
    </i>
  )
}

// Le bandeau en bas de l'écran, une ligne par vidéo qui avance (chaque
// écran a ses lignes, qui suivent chacune leur vidéo). `pleinEcran` : collé
// au bas de l'écran (Timer), sinon au-dessus de la barre du bas.
export function BandeauAvancement({ children, pleinEcran = false }) {
  return (
    <div className={pleinEcran ? 'avancement avancement--plein-ecran' : 'avancement'} role="status">
      {children}
    </div>
  )
}

export function LigneAvancement({ nom, texte, pourcent, etape = 'envoi', bloque = false }) {
  return (
    <div className={`avancement__ligne avancement__ligne--${etape}`}>
      <span>
        {bloque && <Tourne />}
        {nom && <b>{nom}</b>}
        <em>{texte}</em>
      </span>
      <BarreAvancement pourcent={pourcent} etape={etape} bloque={bloque} />
    </div>
  )
}
