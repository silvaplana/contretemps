import { useEffect, useRef, useState } from 'react'
import { reduirePhoto } from '../../../utils/reduirePhoto.js'

// Feuille d'émargement, le jour de l'AG (spec procurations.md §4, étape 2) :
// une ligne par membre convoqué, une touche = présent (Annuler 10 s), le
// quorum en direct. Le décompte vient du serveur : un pouvoir compte si son
// mandataire est présent, un mandant présent reprend sa voix.
// En tête, « Prendre en photo la liste des présents » (proces-verbal-ag.md §1) :
// la feuille signée à l'entrée est lue, on vérifie les noms en doute, puis
// on pointe tout le monde d'un coup.

const QUORUM = { quarter: 'un quart', third: 'un tiers', half: 'la moitié' }
const ANNULER_MS = 10000
const sansAccents = (t) => String(t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

export default function Emargement({ file, api, onClose, onToast }) {
  const [s, setS] = useState(null)
  const [cherche, setCherche] = useState('')
  const [dernier, setDernier] = useState(null) // { person_id, name, present }
  const [ajout, setAjout] = useState(false)
  const [trouves, setTrouves] = useState([])
  const minuteur = useRef(null)
  const choixPhoto = useRef(null)
  const [lecture, setLecture] = useState(null) // { sure, doubts, unknown, photos }
  const [lit, setLit] = useState(false)

  useEffect(() => {
    api.attendance(file.id).then(setS, (e) => onToast(e.message))
  }, [api, file.id, onToast])
  useEffect(() => () => clearTimeout(minuteur.current), [])
  useEffect(() => {
    if (!ajout || cherche.trim().length < 2) return
    let actif = true
    api.principals(cherche.trim()).then((r) => actif && setTrouves(r.filter((p) => p.type === 'member')), () => {})
    return () => {
      actif = false
    }
  }, [api, ajout, cherche])

  async function pointer(personId, name, present, annulable = true) {
    try {
      setS(await api.mark(file.id, personId, present))
      clearTimeout(minuteur.current)
      if (annulable) {
        setDernier({ person_id: personId, name, present })
        minuteur.current = setTimeout(() => setDernier(null), ANNULER_MS)
      } else setDernier(null)
    } catch (e) {
      onToast(e.message)
    }
  }

  async function lirePhotos(fichiers) {
    if (!fichiers.length) return
    setLit(true)
    try {
      const pages = await Promise.all(fichiers.map(reduirePhoto))
      setLecture({ ...(await api.readAttendancePhoto(file.id, pages)), choix: {} })
    } catch (e) {
      onToast(e.message)
    } finally {
      setLit(false)
    }
  }

  if (!s) return <div className="dx-panel" role="dialog" aria-label="Feuille d’émargement" aria-busy="true" />

  if (lecture) {
    return (
      <VerifierListe
        lecture={lecture}
        setLecture={setLecture}
        onClose={() => setLecture(null)}
        onValider={async (ids) => {
          try {
            setS(await api.markMany(file.id, ids))
            setLecture(null)
            onToast(`${ids.length} présent${ids.length > 1 ? 's' : ''} pointé${ids.length > 1 ? 's' : ''}`)
          } catch (e) {
            onToast(e.message)
          }
        }}
      />
    )
  }

  const filtre = sansAccents(cherche.trim())
  const lignes = filtre ? s.rows.filter((r) => sansAccents(r.name).includes(filtre)) : s.rows
  const connus = new Set(s.rows.map((r) => String(r.person_id)))
  const q = s.quorum

  return (
    <div className="dx-panel em" role="dialog" aria-label="Feuille d’émargement">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
        <h2>Feuille d’émargement</h2>
      </div>
      <div className="em-haut">
        <div className="em-chiffres">
          <span><b>{s.present}</b> présents</span>
          <span><b>{s.represented}</b> représentés</span>
          <span><b>{s.votes}</b> voix</span>
        </div>
        <p className={`em-quorum${q ? (q.reached ? ' em-quorum--ok' : ' em-quorum--non') : ''}`}>
          {q
            ? `Quorum : ${q.votes} voix sur ${q.needed} nécessaires (${QUORUM[q.rule]} des ${s.convoked} membres). ${q.reached ? 'Atteint.' : 'Pas atteint.'}`
            : `${s.votes} voix présentes ou représentées sur ${s.convoked} membres convoqués.`}
          {s.lost > 0 && ` ${s.lost} pouvoir${s.lost > 1 ? 's' : ''} perdu${s.lost > 1 ? 's' : ''}.`}
        </p>
        <input
          ref={choixPhoto}
          type="file"
          accept="image/*,application/pdf"
          multiple
          hidden
          onChange={(e) => {
            lirePhotos([...e.target.files])
            e.target.value = ''
          }}
        />
        <button type="button" className="dx-btn dx-btn--ghost em-photo" disabled={lit} onClick={() => choixPhoto.current?.click()}>
          {lit ? 'Lecture de la liste…' : '📷 Prendre en photo la liste des présents'}
        </button>
        <input
          className="ap-input"
          type="search"
          placeholder={ajout ? 'Nom de la personne à ajouter' : 'Chercher un membre'}
          aria-label="Chercher"
          value={cherche}
          onChange={(e) => setCherche(e.target.value)}
        />
      </div>
      <div className="dx-body em-liste">
        {ajout ? (
          <>
            {trouves
              .filter((p) => !connus.has(String(p.id)))
              .map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="em-ligne"
                  onClick={async () => {
                    await pointer(Number(p.id), p.label, true)
                    setAjout(false)
                    setCherche('')
                  }}
                >
                  <span className="em-nom">{p.label}</span>
                  <small>{p.detail || 'Ajouter, présent'}</small>
                </button>
              ))}
            {cherche.trim().length < 2 && <p className="dx-note">Tapez au moins deux lettres du nom.</p>}
          </>
        ) : (
          <>
            {lignes.map((r) => (
              <button
                key={r.person_id}
                type="button"
                className={`em-ligne${r.present ? ' em-ligne--on' : ''}`}
                aria-pressed={r.present}
                onClick={() => pointer(r.person_id, r.name, !r.present)}
              >
                <span className="em-coche" aria-hidden="true">{r.present ? '✓' : ''}</span>
                <span className="em-nom">
                  {r.name}
                  <small>
                    {r.present
                      ? `Présent${r.holds ? ` · porte ${r.holds} pouvoir${r.holds > 1 ? 's' : ''}` : ''}${r.convoked ? '' : ' · non convoqué'}`
                      : r.represented_by
                        ? `Représenté par ${r.represented_by}`
                        : r.proxy_name
                          ? `Pouvoir à ${r.proxy_name}, perdu s’il ne vient pas`
                          : r.answer === 'attend'
                          ? 'A dit qu’il viendrait'
                          : r.answer === 'absent'
                            ? 'A dit qu’il ne viendrait pas'
                            : ''}
                    {r.lost.length > 0 && ` · pouvoir perdu de ${r.lost.join(', ')}`}
                  </small>
                </span>
              </button>
            ))}
            {lignes.length === 0 && <p className="dx-note">Personne à ce nom.</p>}
          </>
        )}
        <button type="button" className="ap-link" onClick={() => (setAjout(!ajout), setCherche(''), setTrouves([]))}>
          {ajout ? 'Revenir à la liste' : '+ Ajouter une personne'}
        </button>
      </div>
      {dernier && (
        <div className="dx-toast" role="status">
          <span>{dernier.name} : {dernier.present ? 'présent' : 'plus présent'}</span>
          <button type="button" onClick={() => pointer(dernier.person_id, dernier.name, !dernier.present, false)}>
            Annuler
          </button>
        </div>
      )}
      <div className="dx-footer">
        <button
          type="button"
          className="dx-btn"
          onClick={async () => {
            try {
              setDernier(null)
              const r = await api.storeSheet(file.id)
              onToast(`« ${r.name} » rangée dans le dossier de l’AG`)
            } catch (e) {
              onToast(e.message)
            }
          }}
        >
          Enregistrer la feuille (PDF)
        </button>
      </div>
    </div>
  )
}

// Après la photo : les noms sûrs, ceux à choisir (homonymes, écriture
// difficile) et ceux qui ne sont pas convoqués. Rien n'est pointé avant
// « Pointer les N présents », qui attend que chaque doute soit tranché.
function VerifierListe({ lecture, setLecture, onClose, onValider }) {
  const { sure, doubts, unknown, choix } = lecture
  const choisir = (i, valeur) => setLecture({ ...lecture, choix: { ...choix, [i]: valeur } })
  const restants = doubts.filter((_, i) => choix[i] === undefined).length
  const ids = [...new Set([...sure.map((p) => p.person_id), ...Object.values(choix).filter((v) => v !== null)])]
  return (
    <div className="dx-panel em" role="dialog" aria-label="Liste des présents">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
        <h2>{sure.length} présent{sure.length > 1 ? 's' : ''} reconnu{sure.length > 1 ? 's' : ''}</h2>
      </div>
      <div className="dx-body em-liste">
        {restants > 0 && (
          <p className="dx-note">{restants === 1 ? 'Vérifiez le nom en jaune.' : `Vérifiez les ${restants} noms en jaune.`}</p>
        )}
        {doubts.map((d, i) => (
          <div key={`d${i}`} className={`em-doute${choix[i] === undefined ? '' : ' em-doute--ok'}`}>
            <span className="em-nom">
              « {d.written} »<small>{d.reason}</small>
            </span>
            <div className="em-choix">
              {d.candidates.map((c) => (
                <button
                  key={c.person_id}
                  type="button"
                  className="dx-btn dx-btn--ghost"
                  aria-pressed={choix[i] === c.person_id}
                  onClick={() => choisir(i, c.person_id)}
                >
                  {c.name}
                </button>
              ))}
              <button type="button" className="dx-btn dx-btn--ghost" aria-pressed={choix[i] === null} onClick={() => choisir(i, null)}>
                Personne
              </button>
            </div>
          </div>
        ))}
        {sure.map((p) => (
          <div key={p.person_id} className="em-ligne em-ligne--on">
            <span className="em-coche" aria-hidden="true">✓</span>
            <span className="em-nom">
              {p.name}
              {p.written !== p.name && <small>écrit « {p.written} »</small>}
            </span>
          </div>
        ))}
        {unknown.length > 0 && (
          <p className="dx-note">
            Pas dans les membres convoqués : {unknown.map((u) => `« ${u.written} »`).join(', ')}. Ajoutez-les ensuite sur la
            feuille si besoin (+ Ajouter une personne).
          </p>
        )}
        <p className="dx-note">La photo est rangée dans le dossier de l’AG.</p>
      </div>
      <div className="dx-footer">
        <button type="button" className="dx-btn" disabled={restants > 0 || ids.length === 0} onClick={() => onValider(ids)}>
          Pointer les {ids.length} présent{ids.length > 1 ? 's' : ''}
        </button>
      </div>
    </div>
  )
}
