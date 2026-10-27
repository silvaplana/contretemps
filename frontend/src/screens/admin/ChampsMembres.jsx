import { useEffect, useRef, useState } from 'react'
import * as champsApi from '../../api/champs.js'
import { MODULES } from '../../app/modules.js'
import Modal from '../../components/Modal.jsx'
import AffichageAdmin from './AffichageAdmin.jsx'

// La fiche d'un membre (spec/core.md §4.3, niveau 1 ; maquette « Champs des
// membres ») : ce que l'école demande à chaque membre, pour la saison
// affichée. Admin > Élèves > ⋮ > Champs. Les champs du socle sont toujours
// là, verrouillés ; les autres s'ajoutent, se règlent et se retirent
// (Annuler 10 s, les réponses sont gardées). « Affichage dans Admin › » mène
// aux colonnes du tableau (AffichageAdmin.jsx).
// En tête, les blocs des modules (`memberFields` du module.js : la campagne
// HelloAsso) ; leurs champs (`source`) sont verrouillés, seuls les réglages
// avancés changent, et cachent les nôtres du même intitulé.

const ANNULER_MS = 10000

const SOCLE = [
  { id: 'nom', label: 'Nom, prénom', required: true, format: 'short_text' },
  { id: 'email', label: 'Email', required: true, format: 'short_text' },
  { id: 'payeur', label: 'Email du payeur', required: false, format: 'short_text' },
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

const BLOCS = MODULES.filter((m) => m.memberFields)

function ligneDe(champ, choix, sources = {}) {
  let format = champsApi.nomFormat(champ.format)
  if (champ.format === 'group') {
    const groupe = choix.parents.find((g) => g.id === champ.group_id)
    format = `Groupe ${groupe?.name ?? ''}${champ.multiple ? ' (plusieurs)' : ''}`
  } else if (champ.format === 'list' && champ.multiple) {
    format = 'Liste (plusieurs)'
  }
  const statut = sources[champ.source]?.ligne ?? (champ.required ? 'Obligatoire' : 'Facultatif')
  return `${statut} · ${format}`
}

export default function ChampsMembres({ ecoleId, onClose }) {
  const [affichage, setAffichage] = useState(false)
  const [champs, setChamps] = useState(null)
  const [choix, setChoix] = useState({ parents: [], audiences: [] })
  const [courant, setCourant] = useState(null) // brouillon du champ ouvert
  const [avance, setAvance] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [toast, setToast] = useState(null)
  const [sources, setSources] = useState({}) // module → { ligne, note } de ses champs
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

  function blocChange(cle, info) {
    setSources((s) => ({ ...s, [cle]: info }))
    relire().catch((e) => setErreur(e.message))
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
    if (courant.verrouille && !courant.source) {
      setCourant(null)
      return
    }
    if (!courant.label.trim()) {
      setErreur('Donnez un intitulé.')
      return
    }
    const { id, verrouille, choicesTexte, position, source, source_key, ...reglages } = courant
    void verrouille
    void position
    void source_key
    reglages.choices = courant.format === 'list' ? choicesTexte.split('\n') : null
    if (source) {
      // Champ d'un module : seuls les réglages avancés partent.
      for (const cle of Object.keys(reglages)) {
        if (!['member_sees', 'member_edits', 'others_see', 'for_group_id'].includes(cle)) delete reglages[cle]
      }
    }
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

  if (affichage) {
    return (
      <AffichageAdmin
        ecoleId={ecoleId}
        champs={champs ?? []}
        onRetour={() => setAffichage(false)}
        onClose={onClose}
      />
    )
  }

  if (courant) {
    const bloque = courant.verrouille || Boolean(courant.source)
    const avancesOuverts = !courant.verrouille
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
          {courant.source && <p className="champs__note">{sources[courant.source]?.note}</p>}
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
            disabled={bloque || Boolean(courant.key)}
            onChange={(e) => changer('format', e.target.value)}
          >
            {champsApi.FORMATS.filter(([cle]) => cle !== 'group' || choix.parents.length > 0).map(([cle, nom]) => (
              <option key={cle} value={cle}>
                {nom}
              </option>
            ))}
          </select>
          {/* Un champ que l'appli lit (l'âge vient de la date de naissance). */}
          {courant.key && <p className="champs__note">L’appli s’en sert : son format ne change pas.</p>}
          {courant.format === 'list' && (
            <>
              <label htmlFor="champ-choix">Choix proposés, un par ligne</label>
              <textarea
                id="champ-choix"
                className="modal-textarea"
                rows={5}
                value={courant.choicesTexte}
                disabled={bloque}
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
                disabled={bloque}
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
              <input
                type="checkbox"
                checked={courant.multiple}
                disabled={bloque}
                onChange={(e) => changer('multiple', e.target.checked)}
              />
              Plusieurs choix possibles
            </label>
          )}
          {avancesOuverts && (
            <button type="button" className="champs__lien" onClick={() => setAvance((a) => !a)}>
              {avance ? '▾' : '›'} Réglages avancés : côté membre
            </button>
          )}
          {avancesOuverts && avance && (
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

  // Un champ d'un module cache le nôtre du même intitulé (maquette).
  const imposes = new Set((champs ?? []).filter((c) => c.source).map((c) => c.label.toLowerCase()))
  const visibles = (champs ?? []).filter((c) => c.source || !imposes.has(c.label.toLowerCase()))

  return (
    <Modal title="La fiche d’un membre" onClose={onClose}>
      <div className="champs">
        <p className="champs__note champs__note--haut">Ce qu’on demande à chaque membre.</p>
        {BLOCS.map((m) => (
          <m.memberFields key={m.key} ecoleId={ecoleId} onChange={(info) => blocChange(m.key, info)} />
        ))}
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
        {visibles.map((champ) => (
          <button key={champ.id} type="button" className="champs__ligne" onClick={() => ouvrir(champ)}>
            <span>
              {champ.label}
              <small>{ligneDe(champ, choix, sources)}</small>
            </span>
            <span className="champs__chevron">›</span>
          </button>
        ))}
        <button type="button" className="btn btn--secondary champs__ajouter" onClick={() => ouvrir(NOUVEAU)}>
          + Ajouter un champ
        </button>
        <button type="button" className="champs__lien" onClick={() => setAffichage(true)}>
          Affichage dans Admin ›
        </button>
      </div>
      {toastAffiche}
    </Modal>
  )
}
