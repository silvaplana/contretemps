import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { ecrire, estEtendu, lire } from './timerReglages.js'

// Fights › ⋮ › Paramètres du Timer (Seb, 21/11). Rien de coché : le Timer
// simple. Une case cochée : le Timer étendu, en paysage. Gardé sur l'appareil.
const CASES = [
  ['film', 'Filmer le combat', 'La cloche lance et arrête le film. À la fin : Archiver, Partager ou Jeter.'],
  ['noms', 'Nommer les combattants', 'Deux noms à taper, avant ou pendant le combat.'],
  ['vainqueur', 'Déclarer le vainqueur', 'On touche le poing levé de celui qui a gagné, ou « = » pour un match nul.'],
]
// Sous « Déclarer le vainqueur », qu'elle suppose (Seb, 21/11).
const ANNONCE = ['annonce', 'Annoncer le vainqueur', 'Au poing levé, un speaker annonce : « And the winner, by unanimous decision, is… » et le nom ; au « = » : « It’s a draw! ».']
// Ce qu'on incruste dans la vidéo archivée (Seb, 21/11, maquette
// https://claude.ai/artifact/EnShfzDt9KyDjydtttA5n4) ; la 3e colonne : la case qu'elle suppose.
const INCRUSTATION = [
  ['incrNoms', 'Les noms au début', 'Ils arrivent chacun de leur côté et se cognent au milieu.', 'noms'],
  ['incrVainqueur', 'Le vainqueur à la fin', 'Après le gong, avec l’annonce si elle est cochée.', 'vainqueur'],
  ['incrChrono', 'Le chrono', 'En chiffres rouges ; R1, R2… s’il y a plusieurs rounds.'],
  ['incrMusique', 'Une musique', 'Choisie en un geste à « Archiver ».'],
]

export default function ParametresTimer({ onBack }) {
  const [r, setR] = useState(lire)
  function cocher(cle, oui) {
    const suite = { ...r, [cle]: oui }
    setR(suite)
    ecrire(suite)
  }
  return (
    <div className="screen sc">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <strong className="sc__titre">Paramètres du Timer</strong>
      </div>
      <div className="sc__corps">
        <p className="sc-te__aide">Sans rien cocher, le Timer reste simple : le temps, la cloche et le chronomètre.</p>
        {[...CASES, ANNONCE].map(([cle, libelle, aide]) => (
          <label key={cle} className={`sc-coche${cle === 'annonce' ? ' sc-te__sous-case' : ''}`}>
            <input
              type="checkbox"
              checked={r[cle] && (cle !== 'annonce' || r.vainqueur)}
              disabled={cle === 'annonce' && !r.vainqueur}
              onChange={(ev) => cocher(cle, ev.target.checked)}
            />
            <span>
              {libelle}
              <small>{aide}</small>
            </span>
          </label>
        ))}
        {r.film && (
          <>
            <p className="sc-te__titre-incr">Dans la vidéo archivée</p>
            {INCRUSTATION.map(([cle, libelle, aide, suppose]) => (
              <label key={cle} className="sc-coche">
                <input
                  type="checkbox"
                  checked={r[cle] && (!suppose || r[suppose])}
                  disabled={suppose && !r[suppose]}
                  onChange={(ev) => cocher(cle, ev.target.checked)}
                />
                <span>
                  {libelle}
                  <small>{aide}</small>
                </span>
              </label>
            ))}
            <p className="sc-te__aide">La vidéo est prête une demi-minute après « Archiver ».</p>
          </>
        )}
        <p className="sc-te__aide">
          <strong>{estEtendu(r) ? 'Timer étendu, téléphone en paysage' : 'Timer simple'}</strong>
        </p>
      </div>
    </div>
  )
}
