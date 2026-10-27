import { useEffect, useRef, useState } from 'react'
import * as champsApi from '../../api/champs.js'
import Modal from '../../components/Modal.jsx'

// La fiche d'un membre (spec/core.md §4.3, niveau 1 ; maquette « Champs des
// membres ») : ce que l'école demande à chaque membre, pour la saison
// affichée. Admin > Élèves > ⋮ > Champs. Les champs du socle sont toujours
// là, verrouillés ; les autres s'ajoutent, se règlent et se retirent
// (Annuler 10 s, les réponses sont gardées). L'affichage dans Admin (les
// colonnes du tableau) viendra ensuite.

const ANNULER_MS = 10000

const SOCLE = [
  { id: 'nom', label: 'Nom, prénom', required: true, format: 'short_text' },
  { id: 'email', label: 'Email', required: true, format: 'short_text' },
  { id: 'telephone', label: 'Téléphone', required: false, format: 'phone' },
]

const NOUVEAU = {
  label: '',
  required: false,
  format: 'short_text',
  choices: null,
  group_id: null,
  multiple: false,
  member_sees: false,
  member_edits: false,
  others_see: false,
  for_group_id: null,
}

function ligneDe(champ, choix) {
  let format = champsApi.nomFormat(champ.format)
  if (champ.format === 'group') {
    const groupe = choix.parents.find((g) => g.id === champ.group_id)
    format = `Groupe ${groupe?.name ?? ''}${champ.multiple ? ' (plusieurs)' : ''}`
  } else if (champ.format === 'list' && champ.multiple) {
    format = 'Liste (plusieurs)'
  }
  return `${champ.required ? 'Obligatoire' : 'Facultatif'} · ${format}`
}

export default function ChampsMembres({ ecoleId, onClose }) {
  const [champs, setChamps] = useState(null)
  const [choix, setChoix] = useState({ parents: [], audiences: [] })
  const [courant, setCourant] = useState(null) // brouillon du champ ouvert
  const [avance, setAvance] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)

  async function relire() {
    const [liste, groupes] = await Promise.all([champsApi.lister(ecoleId), champsApi.groupes(ecoleId)])
    setChamps(liste)
    setChoix(groupes)
  }

  useEffect(() => {
    relire().catch(() => setErreur('Impossible de charger la fiche : vérifiez la connexion.'))
    return () => clearTimeout(minuteur.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecoleId])

  function montrerToast(texte, annuler) {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), ANNULER_MS)
  }

  function ouvrir(champ, verrouille = false) {
    setCourant({ ...champ, verrouille, choicesTexte: (champ.choices ?? []).join('\n') })
    setAvance(false)
    setErreur('')
  }

  function changer(cle, valeur) {
    setCourant((c) => ({ ...c, [cle]: valeur }))
  }

  async function valider() {
    if (courant.verrouille) {
      setCourant(null)
      return
    }
    if (!courant.label.trim()) {
      setErreur('Donnez un intitulé.')
      return
    }
    const { id, verrouille, choicesTexte, position, ...reglages } = courant
    void verrouille
    void position
    reglages.choices = courant.format === 'list' ? choicesTexte.split('\n') : null
    if (courant.format === 'group' && !reglages.group_id) reglages.group_id = choix.parents[0]?.id ?? null
    setEnCours(true)
    setErreur('')
    try {
      if (id) await champsApi.modifier(id, reglages)
      else await champsApi.creer(ecoleId, reglages)
      await relire()
      setCourant(null)
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  async function retirerCourant() {
    const champ = courant
    setEnCours(true)
    try {
      await champsApi.retirer(champ.id)
      await relire()
      setCourant(null)
      montrerToast(`« ${champ.label} » retiré, ses réponses sont gardées`, async () => {
        await champsApi.remettre(champ.id)
        await relire()
      })
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  const toastAffiche = toast && (
    <div className="admin-groupes__toast" role="status">
      <span>{toast.texte}</span>
      {toast.annuler && (
        <button
          type="button"
          onClick={() => {
            const annuler = toast.annuler
            setToast(null)
            clearTimeout(minuteur.current)
            annuler().catch((e) => setErreur(e.message))
          }}
        >
          Annuler
        </button>
      )}
    </div>
  )

  if (courant) {
    const bloque = courant.verrouille
    return (
      <Modal
        title={courant.label || 'Nouveau champ'}
        onClose={onClose}
        footer={
          <>
            {erreur && <p className="login-screen__erreur">{erreur}</p>}
            <button type="button" className="btn btn--primary champs__principal" disabled={enCours} onClick={valider}>
              OK
            </button>
            {courant.id && !bloque && (
              <button type="button" className="champs__lien" disabled={enCours} onClick={retirerCourant}>
                Retirer ce champ
              </button>
            )}
          </>
        }
      >
        <div className="champs form-fields">
          <button type="button" className="champs__lien champs__retour" onClick={() => setCourant(null)}>
            ← La fiche d’un membre
          </button>
          <label htmlFor="champ-intitule">Intitulé</label>
          <input
            id="champ-intitule"
            className="field-input"
            value={courant.label}
            placeholder="ex. Taille de t-shirt"
            disabled={bloque}
            onChange={(e) => changer('label', e.target.value)}
          />
          <label>Statut</label>
          <div className="champs__seg" role="group" aria-label="Statut">
            {[
              [true, 'Obligatoire'],
              [false, 'Facultatif'],
            ].map(([valeur, libelle]) => (
              <button
                key={libelle}
                type="button"
                aria-pressed={courant.required === valeur}
                disabled={bloque}
                onClick={() => changer('required', valeur)}
              >
                {libelle}
              </button>
            ))}
          </div>
          <label htmlFor="champ-format">Format de la réponse</label>
          <select
            id="champ-format"
            className="field-input"
            value={courant.format}
            disabled={bloque}
            onChange={(e) => changer('format', e.target.value)}
          >
            {champsApi.FORMATS.filter(([cle]) => cle !== 'group' || choix.parents.length > 0).map(([cle, nom]) => (
              <option key={cle} value={cle}>
                {nom}
              </option>
            ))}
          </select>
          {courant.format === 'list' && (
            <>
              <label htmlFor="champ-choix">Choix proposés, un par ligne</label>
              <textarea
                id="champ-choix"
                className="modal-textarea"
                rows={5}
                value={courant.choicesTexte}
                onChange={(e) => changer('choicesTexte', e.target.value)}
              />
            </>
          )}
          {courant.format === 'group' && (
            <>
              <label htmlFor="champ-groupe">Parmi les groupes de</label>
              <select
                id="champ-groupe"
                className="field-input"
                value={courant.group_id ?? choix.parents[0]?.id ?? ''}
                onChange={(e) => changer('group_id', Number(e.target.value))}
              >
                {choix.parents.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
              <p className="champs__note">
                Ex. « Cours suivis » : on coche les cours de la personne, et elle entre dans ces groupes.
              </p>
            </>
          )}
          {(courant.format === 'list' || courant.format === 'group') && (
            <label className="champs__case">
              <input type="checkbox" checked={courant.multiple} onChange={(e) => changer('multiple', e.target.checked)} />
              Plusieurs choix possibles
            </label>
          )}
          {!bloque && (
            <button type="button" className="champs__lien" onClick={() => setAvance((a) => !a)}>
              {avance ? '▾' : '›'} Réglages avancés : côté membre
            </button>
          )}
          {!bloque && avance && (
            <>
              <p className="champs__note">Les admins voient toujours tout. Ici, c’est ce que voient les membres.</p>
              <label className="champs__case">
                <input
                  type="checkbox"
                  checked={courant.member_sees}
                  onChange={(e) =>
                    setCourant((c) => ({
                      ...c,
                      member_sees: e.target.checked,
                      ...(e.target.checked ? {} : { member_edits: false, others_see: false }),
                    }))
                  }
                />
                La personne le voit dans sa fiche
              </label>
              <label className="champs__case">
                <input
                  type="checkbox"
                  checked={courant.member_edits}
                  disabled={!courant.member_sees}
                  onChange={(e) => changer('member_edits', e.target.checked)}
                />
                La personne peut le modifier
              </label>
              <label className="champs__case">
                <input
                  type="checkbox"
                  checked={courant.others_see}
                  disabled={!courant.member_sees}
                  onChange={(e) => changer('others_see', e.target.checked)}
                />
                Les autres membres le voient
              </label>
              <label htmlFor="champ-pour">Pour qui</label>
              <select
                id="champ-pour"
                className="field-input"
                value={courant.for_group_id ?? ''}
                onChange={(e) => changer('for_group_id', e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Tous les membres</option>
                {choix.audiences.map((g) => (
                  <option key={g.id} value={g.id}>
                    Seulement le groupe {g.name}
                  </option>
                ))}
              </select>
            </>
          )}
        </div>
        {toastAffiche}
      </Modal>
    )
  }

  return (
    <Modal title="La fiche d’un membre" onClose={onClose}>
      <div className="champs">
        <p className="champs__note champs__note--haut">Ce qu’on demande à chaque membre.</p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        <div className="champs__entete">Champ · statut · format</div>
        {SOCLE.map((champ) => (
          <button key={champ.id} type="button" className="champs__ligne" onClick={() => ouvrir(champ, true)}>
            <span>
              {champ.label}
              <small>{ligneDe(champ, choix)}</small>
            </span>
            <span className="champs__chevron">›</span>
          </button>
        ))}
        {(champs ?? []).map((champ) => (
          <button key={champ.id} type="button" className="champs__ligne" onClick={() => ouvrir(champ)}>
            <span>
              {champ.label}
              <small>{ligneDe(champ, choix)}</small>
            </span>
            <span className="champs__chevron">›</span>
          </button>
        ))}
        <button type="button" className="btn btn--secondary champs__ajouter" onClick={() => ouvrir(NOUVEAU)}>
          + Ajouter un champ
        </button>
      </div>
      {toastAffiche}
    </Modal>
  )
}
