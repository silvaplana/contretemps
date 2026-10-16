import { useEffect, useRef, useState } from 'react'

// Dictée de l'assistant (demande de Seb, 2026-10-16) : la reconnaissance
// vocale du navigateur (Web Speech API), gratuite et sans rien sur notre
// serveur. Chrome et Edge l'envoient aux serveurs de Google ou Microsoft,
// Safari la fait avec celle d'Apple. Absente de Firefox : le bouton micro
// n'apparaît alors pas.
const Reconnaissance = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

export const dicteeDisponible = Boolean(Reconnaissance)

// `texteActuel()` : ce qui est déjà écrit au moment où l'on commence à
// parler ; `ecrire(texte)` : le champ, complété au fur et à mesure.
export function useDictee(texteActuel, ecrire) {
  const [ecoute, setEcoute] = useState(false)
  const [erreur, setErreur] = useState(null)
  // On entend une voix : les ondes s'agitent davantage.
  const [parle, setParle] = useState(false)
  const reco = useRef(null)

  useEffect(() => () => reco.current?.abort(), [])

  function demarrer() {
    if (!Reconnaissance || reco.current) return
    setErreur(null)
    const r = new Reconnaissance()
    r.lang = 'fr-FR'
    r.continuous = true
    r.interimResults = true
    const debut = texteActuel()
    const avant = debut && !/\s$/.test(debut) ? `${debut} ` : debut
    let definitif = ''
    r.onresult = (e) => {
      let provisoire = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) definitif += e.results[i][0].transcript
        else provisoire += e.results[i][0].transcript
      }
      ecrire(avant + definitif + provisoire)
    }
    r.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') setErreur('Micro refusé : autorisez-le dans le navigateur.')
      else if (e.error !== 'aborted' && e.error !== 'no-speech') setErreur('La dictée s’est interrompue.')
    }
    r.onspeechstart = () => setParle(true)
    r.onspeechend = () => setParle(false)
    r.onend = () => {
      reco.current = null
      setEcoute(false)
      setParle(false)
    }
    reco.current = r
    r.start()
    setEcoute(true)
  }

  function arreter() {
    reco.current?.stop()
  }

  return { ecoute, parle, erreur, basculer: () => (reco.current ? arreter() : demarrer()), arreter }
}
