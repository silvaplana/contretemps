import { useEffect, useRef, useState } from 'react'

// Dictée de l'assistant (demande de Seb, 2026-10-16) : la reconnaissance
// vocale du navigateur (Web Speech API), gratuite et sans rien sur notre
// serveur. Chrome et Edge l'envoient aux serveurs de Google ou Microsoft,
// Safari la fait avec celle d'Apple. Absente de Firefox : le bouton micro
// n'apparaît alors pas.
const Reconnaissance = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

export const dicteeDisponible = Boolean(Reconnaissance)

const normaliser = (t) => t.trim().toLowerCase()

// Chrome sur Android (bug signalé par Seb, 2026-10-18 : sur téléphone, en
// bégayant, les mots se répètent) renvoie des morceaux cumulatifs : « je »,
// puis « je voudrais », puis « je voudrais un groupe », chacun dans son
// propre résultat, avec un `resultIndex` peu fiable. Les additionner écrit
// « je je voudrais je voudrais un groupe ». On garde donc un morceau qui
// prolonge le précédent à sa place, et on ignore celui que le précédent
// contient déjà. Sur ordinateur, les morceaux se suivent sans se répéter et
// rien ne change.
export function assembler(resultats) {
  const morceaux = []
  for (let i = 0; i < resultats.length; i++) {
    const texte = resultats[i][0].transcript.trim()
    if (!texte) continue
    const precedent = morceaux.length ? normaliser(morceaux[morceaux.length - 1]) : null
    const courant = normaliser(texte)
    if (precedent !== null && courant.startsWith(precedent)) morceaux[morceaux.length - 1] = texte
    else if (precedent !== null && precedent.includes(courant)) continue
    else morceaux.push(texte)
  }
  return morceaux.join(' ')
}

// `texteActuel()` : ce qui est déjà écrit au moment où l'on commence à
// parler ; `ecrire(texte)` : le champ, complété au fur et à mesure.
//
// Chrome sur Android (bug signalé par Seb, 2026-10-19 : « on ne peut pas
// parler plus de la première ligne ») ignore `continuous` : l'écoute
// s'arrête d'elle-même après chaque phrase. On écoute donc une phrase à la
// fois et on relance tout de suite, jusqu'à « Arrêter la dictée » ou un
// long silence (SILENCES_MAX écoutes sans rien entendre). Même chose sur
// ordinateur, pour n'avoir qu'une façon de faire.
const SILENCES_MAX = 2

export function useDictee(texteActuel, ecrire) {
  const [ecoute, setEcoute] = useState(false)
  const [erreur, setErreur] = useState(null)
  // On entend une voix : les ondes s'agitent davantage.
  const [parle, setParle] = useState(false)
  const reco = useRef(null)
  // L'utilisateur veut encore dicter : une écoute finie est relancée.
  const voulue = useRef(false)
  const silences = useRef(0)
  // Le texte écrit par la phrase précédente : la suivante repart de là, même
  // si le champ n'a pas encore été redessiné.
  const ecrit = useRef(null)

  useEffect(
    () => () => {
      voulue.current = false
      reco.current?.abort()
    },
    [],
  )

  function ecouterUnePhrase() {
    const r = new Reconnaissance()
    r.lang = 'fr-FR'
    r.continuous = false
    r.interimResults = true
    const debut = ecrit.current ?? texteActuel()
    const avant = debut && !/\s$/.test(debut) ? `${debut} ` : debut
    // Le texte est reconstruit à chaque fois depuis tous les morceaux
    // entendus, plutôt qu'ajouté morceau par morceau : voir `assembler`.
    r.onresult = (e) => {
      silences.current = 0
      ecrit.current = avant + assembler(e.results)
      ecrire(ecrit.current)
    }
    r.onerror = (e) => {
      if (e.error === 'no-speech') {
        silences.current += 1
        if (silences.current >= SILENCES_MAX) voulue.current = false
        return
      }
      voulue.current = false
      if (e.error === 'aborted') return
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') setErreur('Micro refusé : autorisez-le dans le navigateur.')
      else setErreur('La dictée s’est interrompue.')
    }
    r.onspeechstart = () => setParle(true)
    r.onspeechend = () => setParle(false)
    r.onend = () => {
      reco.current = null
      setParle(false)
      if (voulue.current) ecouterUnePhrase()
      else setEcoute(false)
    }
    reco.current = r
    r.start()
  }

  function demarrer() {
    if (!Reconnaissance || reco.current) return
    setErreur(null)
    voulue.current = true
    silences.current = 0
    ecrit.current = null
    ecouterUnePhrase()
    setEcoute(true)
  }

  function arreter() {
    voulue.current = false
    reco.current?.stop()
  }

  return { ecoute, parle, erreur, basculer: () => (reco.current ? arreter() : demarrer()), arreter }
}
