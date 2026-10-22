// Le trait de signature au doigt, lissé comme l'encre d'une visionneuse PDF :
// tous les points captés par l'écran (getCoalescedEvents, pas seulement un
// par image), reliés par des courbes qui passent par le milieu de chaque
// segment au lieu de lignes droites anguleuses.

export const pointsDe = (e) => {
  const tous = e.nativeEvent.getCoalescedEvents?.()
  return tous?.length ? tous : [e.nativeEvent]
}

export function debutTrait(p) {
  return { prec: p, milieu: p }
}

export function suiteTrait(ctx, t, p) {
  const milieu = [(t.prec[0] + p[0]) / 2, (t.prec[1] + p[1]) / 2]
  ctx.beginPath()
  ctx.moveTo(...t.milieu)
  ctx.quadraticCurveTo(...t.prec, ...milieu)
  ctx.stroke()
  t.prec = p
  t.milieu = milieu
}

export function finTrait(ctx, t) {
  ctx.beginPath()
  ctx.moveTo(...t.milieu)
  ctx.lineTo(...t.prec)
  ctx.stroke()
}
