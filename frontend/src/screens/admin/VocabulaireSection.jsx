import { useState } from 'react'
import { mettreAJour, useApparence } from '../../api/apparence.js'
import * as personnalisationApi from '../../api/personnalisation.js'

// Où chaque mot s'affiche, sous son champ (Seb, 24 octobre).
const MOTS = [
  { cle: 'motEcole', defaut: 'École', ou: 'S’affiche dans Admin : le nom du premier sous-onglet.' },
  { cle: 'motEleves', defaut: 'Élèves', ou: 'S’affiche dans Admin : le nom du sous-onglet de la liste des élèves.' },
  { cle: 'motCours', defaut: 'Cours', ou: 'S’affiche dans Admin : le nom du sous-onglet des cours.' },
]

// « Vocabulaire » (Admin > École > Personnalisation de l'application ; Seb,
// 24 octobre) : les mots que l'école affiche à la place de École, Élèves et
// Cours. Un champ vidé reprend le mot par défaut.
export default function VocabulaireSection({ ecole }) {
  const apparence = useApparence()
  const [mots, setMots] = useState(() => Object.fromEntries(MOTS.map((m) => [m.cle, apparence[m.cle]])))
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  async function enregistrer() {
    setErreur('')
    setEnCours(true)
    try {
      const vue = await personnalisationApi.modifierVocabulaire(ecole.id, mots)
      mettreAJour(vue)
      setMots(Object.fromEntries(MOTS.map((m) => [m.cle, vue[m.cle]])))
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="perso perso__sous-partie">
      {MOTS.map((m) => (
        <div key={m.cle}>
          <label htmlFor={`vocabulaire-${m.cle}`} className="perso__label">
            {m.defaut}
          </label>
          <input
            id={`vocabulaire-${m.cle}`}
            className="field-input"
            maxLength={30}
            value={mots[m.cle]}
            onChange={(e) => setMots((avant) => ({ ...avant, [m.cle]: e.target.value }))}
          />
          <p className="muted vocabulaire__ou">{m.ou}</p>
        </div>
      ))}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <div className="perso__actions">
        <button type="button" className="btn btn--primary" disabled={enCours} onClick={enregistrer}>
          Enregistrer
        </button>
      </div>
    </div>
  )
}
