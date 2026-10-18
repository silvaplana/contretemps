import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { decouperSurlignage, estStaff, initiales } from './personnes.js'

// D'où vient une personne dans le groupe (spec §3.2).
function origine(p) {
  if (p.moi) return 'Vous, créateur du groupe'
  const parts = []
  if (p.directe) parts.push('Ajoutée directement')
  if (p.parCours.length > 0) parts.push(`Par ${p.parCours.join(', ')}`)
  return parts.join(' · ')
}

// « Qui est dans le groupe ? » (spec/modules/messagerie-instantanee.md
// §3.2-3.3), ouvert par l'œil de « Nouveau groupe » : toutes les personnes
// à plat, cours remplacés par leurs élèves et leurs profs (voir
// personnesDuGroupe). Lecture seule ; la recherche réduit la liste et
// surligne la partie trouvée.
export default function QuiEstDansLeGroupeScreen({ personnes, onBack }) {
  const [recherche, setRecherche] = useState('')
  const actif = recherche.trim() !== ''
  const lignes = personnes
    .map((p) => ({ p, morceaux: decouperSurlignage(`${p.prenom} ${p.nom}`, recherche) }))
    .filter(({ morceaux }) => !actif || morceaux)

  return (
    <div className="ecran-dessus">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour au groupe">
          <Icon name="chevronLeft" size={22} />
        </button>
        <span className="thread-screen__header-text">
          <strong>Qui est dans le groupe ?</strong>
          <span className="muted">
            {personnes.length} personne{personnes.length > 1 ? 's' : ''}
          </span>
        </span>
      </div>

      <div className="ecran-dessus__liste">
        <div className="search-bar choix-membres__recherche">
          <Icon name="search" size={18} />
          <input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher une personne" />
        </div>

        {lignes.map(({ p, morceaux }) => (
          <div key={p.id} className="conversation-list__item nouvelle-discussion__ligne">
            <span className={`avatar nouvelle-discussion__rond ${estStaff(p.role) ? 'avatar--staff' : ''}`}>
              {initiales(p)}
            </span>
            <span className="conversation-list__text">
              <strong>
                {morceaux ? (
                  <>
                    {morceaux[0]}
                    <mark className="surlignage">{morceaux[1]}</mark>
                    {morceaux[2]}
                  </>
                ) : (
                  `${p.prenom} ${p.nom}`
                )}
              </strong>
              <span className="muted">{origine(p)}</span>
            </span>
          </div>
        ))}
        {lignes.length === 0 && <p className="muted">Personne de ce nom dans le groupe.</p>}
      </div>
    </div>
  )
}
