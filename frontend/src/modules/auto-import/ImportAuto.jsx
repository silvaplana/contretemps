import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as drivesApi from '../drives/api.js'
import * as api from './api.js'
import './import-auto.css'

// Financier › Pièces › ⋯ › Importation automatique de pièces (spec/modules/import-auto-pieces.md
// §3, §4 ; maquette https://claude.ai/artifact/PetMSgswm6ZVCH9Wnthqbe) :
// le tableau des imports, la fiche d'un import, « Voir » ses pièces.

const ANNULER_MS = 10000
const NATURES = [
  { value: 'achat', label: 'Facture d’achat' },
  { value: 'vente', label: 'Vente' },
  { value: 'frais', label: 'Note de frais' },
  { value: 'honoraires', label: 'Honoraires' },
  { value: 'salaire', label: 'Paie' },
]
// Source dossier (Seb, 21/11) : pas de destination, le fichier est renommé sur place.
const DOSSIER = ['docs', 'drive']
const FREQUENCES = [
  { value: 'hourly', label: 'Chaque heure' },
  { value: 'daily', label: 'Chaque jour' },
  { value: 'weekly', label: 'Chaque semaine' },
  { value: 'monthly', label: 'Chaque mois' },
]
const euros = (c) => (c / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

// Les lieux possibles : « docs », « drive:<id> », « mail:<id> », « helloasso », « none ».
function lieux(etat, cote) {
  const liste = cote === 'target' ? [{ value: 'none', label: 'Aucune' }] : []
  liste.push({ value: 'docs', label: 'Docs' })
  for (const d of etat.drives) liste.push({ value: `drive:${d.id}`, label: `Drive « ${d.name} »` })
  if (cote === 'source') {
    liste.push({ value: 'helloasso', label: 'HelloAsso (versements)' })
    for (const b of etat.mail_boxes) liste.push({ value: `mail:${b.id}`, label: `Boîte mail « ${b.name} »` })
  }
  return liste
}
const lieuDe = (kind, ref) => (kind === 'drive' || kind === 'mail' ? `${kind}:${ref}` : kind)
function versRegle(valeur) {
  const [kind, ref] = valeur.split(':')
  return { kind, ref: ref ? Number(ref) : null }
}

// Choisir un dossier : Docs (par identifiant) ou un drive (par chemin).
function ChoixDossier({ ecoleId, kind, driveId, valeur, onChoix }) {
  const [pile, setPile] = useState([]) // [{ id | path, name }]
  const [enfants, setEnfants] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [ouvert, setOuvert] = useState(false)
  const courant = pile[pile.length - 1]
  const racine = kind === 'docs' ? 'Docs' : 'Drive'

  useEffect(() => {
    if (!ouvert) return
    setEnfants(null)
    const lire =
      kind === 'docs'
        ? api.dossiersDocs(courant?.id).then((l) => l.map((n) => ({ id: n.id, name: n.name })))
        : drivesApi.lister(ecoleId, driveId, courant?.path ?? '').then((l) =>
            l.filter((e) => e.is_dir).map((e) => ({ path: e.path, name: e.name })),
          )
    lire.then(setEnfants, (e) => setErreur(e.message))
  }, [ouvert, ecoleId, kind, driveId, courant])

  if (!ouvert)
    return (
      <span className="ai__ligne">
        <span className="ai__chemin">
          {valeur ? [racine, ...valeur.split('/')].join(' › ') : 'Aucun dossier choisi'}
        </span>
        <button type="button" className="mail__lien" onClick={() => setOuvert(true)}>
          Choisir
        </button>
      </span>
    )
  return (
    <div className="ai__dossiers">
      <p className="ai__chemin">{[racine, ...pile.map((p) => p.name)].join(' › ')}</p>
      {pile.length > 0 && (
        <button type="button" className="mail__lien" onClick={() => setPile(pile.slice(0, -1))}>
          ← Dossier au-dessus
        </button>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {enfants === null && !erreur && <p className="mail__discret">Lecture…</p>}
      {enfants?.length > 0 && (
        <p className="mail__discret">
          {courant ? `« Choisir » range directement dans « ${courant.name} » ; ou ouvrez un sous-dossier :` : 'Ouvrez un dossier :'}
        </p>
      )}
      {enfants?.map((e) => (
        <button key={e.id ?? e.path} type="button" className="ai__dossier" onClick={() => setPile([...pile, e])}>
          📁 {e.name}
        </button>
      ))}
      {enfants?.length === 0 && <p className="mail__discret">Pas de sous-dossier.</p>}
      <span className="ai__ligne">
        <button type="button" className="btn btn--secondary" onClick={() => setOuvert(false)}>
          Annuler
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={!courant}
          onClick={() => {
            onChoix({ id: courant.id ?? null, path: pile.map((p) => p.name).join('/') })
            setOuvert(false)
          }}
        >
          Choisir « {courant?.name ?? '…'} »
        </button>
      </span>
    </div>
  )
}

function Lieu({ etat, cote, regle, onChange }) {
  const kind = regle[`${cote}_kind`]
  const ref = regle[`${cote}_ref`]
  const chemin = regle[`${cote}_path`]
  const mail = regle.source_kind === 'mail'
  const options = lieux(etat, cote).filter((o) => !(cote === 'target' && mail && o.value === 'none'))
  return (
    <>
      <label className="mail__champ">
        <span>{cote === 'source' ? 'Où lire les pièces' : 'Où ranger le document'}</span>
        <select
          value={lieuDe(kind, ref)}
          onChange={(e) => {
            const { kind: k, ref: r } = versRegle(e.target.value)
            const suite = { [`${cote}_kind`]: k, [`${cote}_ref`]: r, [`${cote}_path`]: '' }
            if (cote === 'source' && k === 'mail' && regle.target_kind === 'none') suite.target_kind = 'docs'
            if (cote === 'source' && k === 'helloasso') suite.nature = 'vente'
            if (cote === 'source' && DOSSIER.includes(k)) Object.assign(suite, { target_kind: 'none', target_ref: null, target_path: '' })
            onChange(suite)
          }}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      {(kind === 'docs' || kind === 'drive') && (
        <ChoixDossier
          key={`${kind}:${ref}`}
          ecoleId={etat.org_id}
          kind={kind}
          driveId={ref}
          valeur={chemin}
          onChoix={({ id, path }) =>
            onChange(kind === 'docs' ? { [`${cote}_ref`]: id, [`${cote}_path`]: path } : { [`${cote}_path`]: path })
          }
        />
      )}
      {cote === 'target' && kind === 'none' && <p className="mail__discret">On lit la source sans produire de document.</p>}
      {cote === 'target' && regle.source_kind === 'helloasso' && (
        <p className="mail__discret">
          <strong>Pièces reconstituées par l’appli</strong> à partir des versements HelloAsso, nommées « … (reconstituée par
          l’appli) ». Pour garder les vraies pièces, prenez comme source le dossier où elles sont déposées.
        </p>
      )}
    </>
  )
}

function Criteres({ regle, onChange }) {
  return (
    <>
      <p className="mail__discret">
        L’appli lit toute la boîte. Un mail devient une pièce s’il a une pièce jointe PDF ou photo (sans pièce jointe, il
        est ignoré), et s’il répond à l’un de ces critères :
      </p>
      <label className="mail__champ">
        <span>L’expéditeur est connu ou contient</span>
        <input
          value={regle.mail_senders}
          placeholder="profs, URSSAF, fournisseurs déjà payés"
          onChange={(e) => onChange({ mail_senders: e.target.value })}
        />
      </label>
      <label className="mail__champ">
        <span>L’objet ou le texte contient</span>
        <input
          value={regle.mail_words}
          placeholder="facture, note d’honoraires, reçu, remboursement"
          onChange={(e) => onChange({ mail_words: e.target.value })}
        />
      </label>
      <label className="ai__case">
        <input type="checkbox" checked={regle.mail_need_amount} onChange={(e) => onChange({ mail_need_amount: e.target.checked })} />
        La pièce jointe montre un montant, une date, un SIRET ou un numéro de facture
      </label>
      <p className="mail__discret">
        La nature vient de l’expéditeur : un prof donne Honoraires, un adhérent qui demande un remboursement donne Note de
        frais ; sinon la nature choisie plus haut.
      </p>
    </>
  )
}

// Source HelloAsso (§4.2) : où va chaque formule de la campagne, dit une fois.
function Formules({ regle, onChange }) {
  const [infos, setInfos] = useState(null)
  const [erreur, setErreur] = useState(null)
  useEffect(() => {
    api.helloasso(regle.season_id).then(setInfos, (e) => setErreur(e.message))
  }, [regle.season_id])
  const comptes = regle.helloasso_accounts ?? {}
  const licences = regle.helloasso_licences ?? {}
  const avecLicence = Object.values(licences).some((c) => c > 0)
  async function ajouterCompte() {
    try {
      const compte = await api.ajouterCompteLicences()
      setInfos({ ...infos, licence_account: compte })
    } catch (e) {
      setErreur(e.message)
    }
  }
  if (erreur) return <p className="mail__discret">{erreur}</p>
  if (!infos) return <p className="mail__discret">Lecture…</p>
  return (
    <>
      <p className="mail__discret">
        Un versement HelloAsso devient une vente, une ligne par compte. Dites une fois où va chaque formule, et
        la part licence à reverser s’il y en a une (prise sur le premier paiement). Un remboursement vient en
        moins dans le versement suivant.
      </p>
      {infos.formulas.length === 0 && <p className="mail__discret">Pas encore d’inscrit HelloAsso pour cette saison.</p>}
      {infos.formulas.map((f) => (
        <div key={f} className="mail__champ">
          <span>{f || 'Sans formule'}</span>
          <select
            aria-label={`Compte de ${f || 'Sans formule'}`}
            value={comptes[f] ?? ''}
            onChange={(e) => onChange({ helloasso_accounts: { ...comptes, [f]: e.target.value ? Number(e.target.value) : null } })}
          >
            <option value="">À choisir</option>
            {infos.accounts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code ? `${c.code} ${c.libelle}` : c.libelle}
              </option>
            ))}
          </select>
          <label className="ai__ligne">
            dont licence
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={licences[f] ? licences[f] / 100 : ''}
              placeholder="0"
              onChange={(e) => {
                const centimes = Math.round(Number(e.target.value.replace(',', '.')) * 100) || 0
                onChange({ helloasso_licences: { ...licences, [f]: Math.max(0, centimes) } })
              }}
            />
            €
          </label>
        </div>
      ))}
      {avecLicence &&
        (infos.licence_account ? (
          <p className="mail__discret">
            Les parts licence vont sur {infos.licence_account.code} {infos.licence_account.libelle}.
          </p>
        ) : (
          <span className="ai__ligne">
            <span className="mail__discret">Le plan comptable n’a pas de compte des licences à reverser.</span>
            <button type="button" className="mail__lien" onClick={ajouterCompte}>
              Ajouter « Licences FFST à reverser » au plan
            </button>
          </span>
        ))}
    </>
  )
}

// Source HelloAsso : destination par défaut Docs › Saison … › Financier › VENTES › COTISATIONS
// (Seb, 20/11), aussi loin que ces dossiers existent (au moins VENTES).
async function dossierCotisations(saison) {
  const pile = []
  const noms = [(n) => n.includes(saison), (n) => n === 'FINANCIER', (n) => n === 'VENTES', (n) => n === 'COTISATIONS']
  for (const convient of noms) {
    const enfants = await api.dossiersDocs(pile[pile.length - 1]?.id)
    const trouve = enfants.find((e) => convient(e.name.toUpperCase()))
    if (!trouve) break
    pile.push(trouve)
  }
  return pile.length >= 3 ? { id: pile[pile.length - 1].id, path: pile.map((p) => p.name).join('/') } : null
}

function Fiche({ etat, regle, onChange, onRetour }) {
  const [message, setMessage] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const saison = etat.seasons.find((s) => s.id === regle.season_id)?.name
  const sansDestination = regle.target_kind === 'none' || (regle.target_kind === 'docs' && !regle.target_ref)
  useEffect(() => {
    if (regle.source_kind !== 'helloasso' || !saison || !sansDestination) return
    let fini = false
    dossierCotisations(saison.toUpperCase()).then(
      (d) => !fini && d && onChange({ target_kind: 'docs', target_ref: d.id, target_path: d.path }),
      () => {},
    )
    return () => {
      fini = true
    }
  }, [regle.source_kind, saison, sansDestination]) // eslint-disable-line react-hooks/exhaustive-deps
  async function regarder() {
    setEnCours(true)
    try {
      const r = await api.regarder(regle.id)
      setMessage(`Regardé à l’instant : ${r.message}.`)
      onChange({}, r.created)
    } catch (e) {
      setMessage(e.message)
    } finally {
      setEnCours(false)
    }
  }
  return (
    <div className="creer-saison" role="dialog" aria-label={regle.name}>
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onRetour} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">{regle.name}</h2>
      </div>
      <div className="creer-saison__corps mail ai">
        <label className="mail__champ">
          <span>Nom</span>
          <input value={regle.name} maxLength={30} onChange={(e) => onChange({ name: e.target.value || ' ' })} />
        </label>
        <label className="mail__champ">
          <span>Nature des pièces créées</span>
          <select value={regle.nature} onChange={(e) => onChange({ nature: e.target.value })}>
            {NATURES.map((n) => (
              <option key={n.value} value={n.value}>
                {n.label}
              </option>
            ))}
          </select>
        </label>
        <label className="mail__champ">
          <span>Saison</span>
          <select
            value={regle.season_id ?? ''}
            onChange={(e) => onChange({ season_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Toutes</option>
            {etat.seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <h3 className="ai__titre">Source</h3>
        <Lieu etat={etat} cote="source" regle={regle} onChange={onChange} />
        {regle.source_kind === 'mail' && <Criteres regle={regle} onChange={onChange} />}
        {regle.source_kind === 'helloasso' && <Formules regle={regle} onChange={onChange} />}
        {DOSSIER.includes(regle.source_kind) ? (
          <p className="mail__discret">
            Chaque fichier reste dans ce dossier, renommé au nom de la pièce : un fichier renommé est traité.
          </p>
        ) : (
          <>
            <h3 className="ai__titre">Destination</h3>
            <Lieu etat={etat} cote="target" regle={regle} onChange={onChange} />
          </>
        )}
        <h3 className="ai__titre">Regarder s’il y a de nouvelles pièces</h3>
        <span className="ai__ligne">
          <select value={regle.frequency} onChange={(e) => onChange({ frequency: e.target.value })}>
            {FREQUENCES.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
          {regle.frequency !== 'hourly' && (
            <label className="ai__ligne">
              à <input type="time" value={regle.at_time} onChange={(e) => onChange({ at_time: e.target.value || '07:00' })} />
            </label>
          )}
        </span>
        <p className="mail__discret">L’appli regarde la source à ce rythme et crée une pièce pour chaque nouveau fichier.</p>
        <button type="button" className="mail__lien" onClick={regarder} disabled={enCours}>
          {enCours ? 'Je regarde…' : 'Regarder maintenant'}
        </button>
        {(message || regle.last_message) && <p className="mail__discret">{message || `Dernier passage : ${regle.last_message}.`}</p>}
        <label className="mail__champ">
          <span>Statut de la pièce créée</span>
          <select value={regle.created_status} onChange={() => {}}>
            <option value="a_valider">À valider</option>
          </select>
        </label>
      </div>
    </div>
  )
}

function Voir({ regle, onRetour }) {
  const [notes, setNotes] = useState(null)
  const [erreur, setErreur] = useState(null)
  useEffect(() => {
    api.pieces(regle.id).then((r) => setNotes(r.notes), (e) => setErreur(e.message))
  }, [regle.id])
  const ou =
    regle.target_kind !== 'none' && !DOSSIER.includes(regle.source_kind)
      ? `Dans la destination : ${regle.target_path || regle.target_kind}`
      : `Dans la source : ${regle.source_path || regle.source_kind}`
  return (
    <div className="creer-saison" role="dialog" aria-label={`Pièces de ${regle.name}`}>
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onRetour} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">{regle.name}</h2>
      </div>
      <div className="creer-saison__corps ai">
        <p className="mail__discret">{ou}</p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        {notes?.map((n) => (
          <div key={n.id} className="ai__piece">
            <span>📄 {n.titre}</span>
            <span className="mail__discret">
              {euros(n.total_centimes ?? 0)} · {n.libelle_statut ?? ''}
            </span>
          </div>
        ))}
        {notes?.length === 0 && <p className="mail__discret">Aucune pièce pour l’instant.</p>}
      </div>
    </div>
  )
}

export default function ImportAuto({ onClose }) {
  const [etat, setEtat] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [ecran, setEcran] = useState(null) // { vue: 'fiche' | 'voir', id }
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)
  const sauvegarde = useRef(null)

  useEffect(() => {
    api.etat().then(setEtat, (e) => setErreur(e.message))
    return () => clearTimeout(minuteur.current)
  }, [])

  const regles = etat?.rules ?? []
  const vue = ecran && regles.find((r) => r.id === ecran.id)

  function changer(id, champs, crees = 0) {
    setEtat((e) => ({
      ...e,
      rules: e.rules.map((r) => (r.id === id ? { ...r, ...champs, pieces: r.pieces + crees } : r)),
    }))
    if (!Object.keys(champs).length) return
    const regle = { ...regles.find((r) => r.id === id), ...champs }
    clearTimeout(sauvegarde.current)
    sauvegarde.current = setTimeout(() => api.enregistrer(regle).catch((e) => setErreur(e.message)), 400)
  }

  async function nouveau() {
    try {
      const r = await api.creer()
      setEtat((e) => ({ ...e, rules: [...e.rules, r] }))
      setEcran({ vue: 'fiche', id: r.id })
    } catch (e) {
      setErreur(e.message)
    }
  }

  // 🗑 : l'import part au bout de 10 s, sauf Annuler ; ses pièces restent.
  function effacer(r) {
    const ancien = etat
    clearTimeout(minuteur.current)
    setEtat({ ...etat, rules: regles.filter((x) => x.id !== r.id) })
    setToast({ texte: `Import « ${r.name} » effacé. Les pièces déjà créées restent.`, ancien })
    minuteur.current = setTimeout(() => {
      setToast(null)
      api.effacer(r.id).catch(() => setEtat(ancien))
    }, ANNULER_MS)
  }

  return createPortal(
    <div className="creer-saison ai-ecran" role="dialog" aria-label="Importation automatique de pièces">
      <div className="thread-screen__header">
        <h2 className="creer-saison__titre">Importation automatique de pièces</h2>
        <button type="button" className="icon-btn ai__fermer" onClick={onClose} aria-label="Fermer">
          <Icon name="x" size={22} />
        </button>
      </div>
      <div className="creer-saison__corps ai">
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        {etat && (
          <table className="ai__table">
            <thead>
              <tr>
                <th>Actif</th>
                <th>Nom</th>
                <th>Saison</th>
                <th className="ai__nombre">Pièces</th>
                <th />
                <th />
              </tr>
            </thead>
            <tbody>
              {regles.map((r) => (
                <tr key={r.id} className={r.active ? '' : 'ai__eteint'} onClick={() => setEcran({ vue: 'fiche', id: r.id })}>
                  <td onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label="Actif"
                      checked={r.active}
                      onChange={(e) => changer(r.id, { active: e.target.checked })}
                    />
                  </td>
                  <td>{r.name}</td>
                  <td>{etat.seasons.find((s) => s.id === r.season_id)?.name ?? 'Toutes'}</td>
                  <td className="ai__nombre">{r.pieces}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {r.pieces > 0 && (
                      <button type="button" className="mail__lien" onClick={() => setEcran({ vue: 'voir', id: r.id })}>
                        Voir
                      </button>
                    )}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button type="button" className="icon-btn" aria-label="Effacer cet import" onClick={() => effacer(r)}>
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {etat && regles.length === 0 && <p className="mail__discret">Aucun import pour l’instant : touchez « + ».</p>}
      </div>
      <button type="button" className="ai__plus" aria-label="Nouvel import" onClick={nouveau}>
        +
      </button>
      {ecran?.vue === 'fiche' && vue && (
        <Fiche etat={etat} regle={vue} onChange={(champs, crees) => changer(vue.id, champs, crees)} onRetour={() => setEcran(null)} />
      )}
      {ecran?.vue === 'voir' && vue && <Voir regle={vue} onRetour={() => setEcran(null)} />}
      {toast && (
        <div className="admin-groupes__toast" role="status">
          <span>{toast.texte}</span>
          <button
            type="button"
            onClick={() => {
              clearTimeout(minuteur.current)
              setEtat(toast.ancien)
              setToast(null)
            }}
          >
            Annuler
          </button>
        </div>
      )}
    </div>,
    document.body,
  )
}
