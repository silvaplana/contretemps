import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import MenuEntete from '../../components/MenuEntete.jsx'
import Modal from '../../components/Modal.jsx'
import * as api from './api.js'
import { prendreJetonEnAttente } from './lienScan.js'
import './essais.css'

// Admin > Essais (spec/modules/essai.md §4, maquette
// https://claude.ai/artifact/3iTgQGr9aJFFyJTuZZ5kcX), repris de l'onglet
// Essai de Sambo Admin : la liste des élèves à l'essai, leur fiche, et la
// page d'essai (§5), et le scan des QR codes au début du cours.

// La caméra et la lecture des QR codes ne se chargent qu'à l'ouverture du scan.
const Scanner = lazy(() => import('./Scanner.jsx'))

const MAX_COURS = 2

function aujourdhuiIso() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

// « 2026-11-18 » -> « 18/11/26 ».
function dateCourte(iso) {
  if (!iso) return ''
  const [a, m, j] = iso.slice(0, 10).split('-')
  return `${j}/${m}/${a.slice(2)}`
}

const dateHeure = (iso) => (iso ? new Date(iso.endsWith('Z') ? iso : `${iso}Z`).toLocaleDateString('fr-FR') : '')
const nom = (s) => `${s.first_name} ${s.last_name}`
const sansAccents = (t) => (t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
const mode = (m) => (m === 'qr' ? 'QR' : 'à la main')
const age = (s) => (s.age != null ? `${s.age} ans` : 'majeur')

// Couleur du nom : vert si le 1er cours est aujourd'hui, orange si un cours
// est déjà fait, rouge si les deux sont faits (comme Sambo Admin).
function etat(s) {
  const [a, b] = [s.course1_date, s.course2_date]
  const jour = aujourdhuiIso()
  if (!a && !b) return 'aucun'
  if (a && b) return b === jour ? 'passe' : 'fini'
  return (a || b) === jour ? 'jour' : 'passe'
}

function Cours({ date, mode: m }) {
  if (!date) return <span className="essais__vide">—</span>
  return (
    <>
      {dateCourte(date)} <span className="essais__pastille">{mode(m)}</span>
    </>
  )
}

export default function Essais({ ecoleId }) {
  const [liste, setListe] = useState(null)
  const [erreur, setErreur] = useState('')
  const [recherche, setRecherche] = useState('')
  const [tous, setTous] = useState(false)
  // Arrivé par un QR code lu avec l'appareil photo : l'écran de scan, avec ce code.
  const [ecran, setEcran] = useState(() => {
    const jeton = prendreJetonEnAttente()
    return jeton ? { nom: 'scan', code: jeton } : { nom: 'liste' }
  })
  const [lien, setLien] = useState('')
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)

  const relire = useCallback(() => {
    api.inscrits(ecoleId).then(
      (l) => {
        setListe(l)
        setErreur('')
      },
      (e) => setErreur(e.message),
    )
  }, [ecoleId])

  useEffect(() => {
    relire()
    api.reglages(ecoleId).then((r) => setLien(r.link), () => {})
  }, [ecoleId, relire])

  function montrer(texte, annuler) {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), annuler ? 10000 : 3000)
  }

  // Cours noté par le scan : la ligne de l'inscrit est mise à jour.
  const noter = useCallback((s) => setListe((l) => l && l.map((x) => (x.id === s.id ? { ...s, member: x.member } : x))), [])

  function remplacer(s) {
    setListe((l) => l.map((x) => (x.id === s.id ? s : x)))
  }

  async function coursAujourdhui(s) {
    try {
      const maj = await api.coursAujourdhui(ecoleId, s.id)
      remplacer(maj)
      const n = s.course1_date ? 2 : 1
      montrer(`${n === 1 ? '1er' : '2e'} cours noté pour ${s.first_name}`, async () => {
        remplacer(await api.modifier(ecoleId, s.id, { [`course${n}_date`]: null }))
      })
    } catch (e) {
      setErreur(e.message)
    }
  }

  // Supprimer : pas de confirmation, « Annuler » pendant 10 s ; la
  // suppression part au bout de ce délai.
  function supprimer(s) {
    setListe((l) => l.filter((x) => x.id !== s.id))
    setEcran({ nom: 'liste' })
    const envoi = setTimeout(() => api.supprimer(ecoleId, s.id).catch((e) => setErreur(e.message)), 10000)
    montrer(`${nom(s)} supprimé`, () => {
      clearTimeout(envoi)
      relire()
    })
  }

  async function copierLien() {
    try {
      await navigator.clipboard.writeText(lien)
      montrer('Lien copié')
    } catch {
      montrer(lien)
    }
  }

  const bandeau = toast && (
    <div className="essais__toast" role="status">
      <span>{toast.texte}</span>
      {toast.annuler && (
        <button
          type="button"
          onClick={async () => {
            const annuler = toast.annuler
            setToast(null)
            try {
              await annuler()
            } catch (e) {
              setErreur(e.message)
            }
          }}
        >
          Annuler
        </button>
      )}
    </div>
  )

  if (ecran.nom === 'fiche') {
    return (
      <>
        <Fiche
          ecoleId={ecoleId}
          id={ecran.id}
          onRetour={() => setEcran({ nom: 'liste' })}
          onChange={remplacer}
          onCours={coursAujourdhui}
          onSupprimer={supprimer}
          liste={liste}
        />
        {bandeau}
      </>
    )
  }
  if (ecran.nom === 'scan') {
    return (
      <Suspense fallback={<p className="muted">Ouverture de la caméra…</p>}>
        <Scanner
          ecoleId={ecoleId}
          code={ecran.code}
          onRetour={() => setEcran({ nom: 'liste' })}
          onNote={noter}
        />
      </Suspense>
    )
  }
  if (ecran.nom === 'reglages') {
    return (
      <>
        <PageEssai ecoleId={ecoleId} onRetour={() => setEcran({ nom: 'liste' })} onCopier={copierLien} onEnregistre={() => montrer("Page d'essai enregistrée")} />
        {bandeau}
      </>
    )
  }

  const cherche = sansAccents(recherche.trim())
  const visibles = (liste ?? []).filter(
    (s) => (tous || !s.member) && (!cherche || sansAccents(`${s.last_name} ${s.first_name} ${s.email}`).includes(cherche)),
  )

  return (
    <div className="admin-panel essais">
      <MenuEntete
        label="Plus d'actions"
        actions={[
          { label: 'Ajouter un inscrit à la main', icon: 'plus', onClick: () => window.open(lien, '_blank', 'noopener') },
          { label: "Page d'essai", icon: 'edit', onClick: () => setEcran({ nom: 'reglages' }) },
          { label: "Copier le lien de la page d'essai", icon: 'copy', onClick: copierLien },
        ]}
      />
      <div className="essais__entete">
        <h2>Élèves à l'essai{liste ? ` (${liste.length})` : ''}</h2>
        <button type="button" className="btn btn--primary" onClick={() => setEcran({ nom: 'scan' })}>
          Scanner les QR codes
        </button>
      </div>
      <input
        id="essais-recherche"
        type="search"
        className="essais__recherche"
        placeholder="Rechercher un inscrit..."
        aria-label="Rechercher un inscrit"
        value={recherche}
        onChange={(e) => setRecherche(e.target.value)}
      />
      <div className="essais__puces" role="group" aria-label="Filtrer">
        <button type="button" aria-pressed={!tous} onClick={() => setTous(false)}>
          Pas encore adhérents
        </button>
        <button type="button" aria-pressed={tous} onClick={() => setTous(true)}>
          Tous
        </button>
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {liste && liste.length === 0 && (
        <p className="muted">Aucun élève à l'essai pour l'instant. Le lien de la page d'essai est dans le menu ⋮.</p>
      )}
      {liste && liste.length > 0 && visibles.length === 0 && <p className="muted">Aucun inscrit ne correspond.</p>}
      {visibles.length > 0 && (
        <div className="table-scroll">
          <table className="data-table essais__table">
            <thead>
              <tr>
                <th>Inscrit</th>
                <th>1er cours</th>
                <th>2e cours</th>
                <th>Âge</th>
                <th>Inscription</th>
                <th>Commentaire</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((s) => (
                <tr key={s.id} className={`essais__ligne essais__ligne--${etat(s)}`} onClick={() => setEcran({ nom: 'fiche', id: s.id })}>
                  <td className="essais__nom">{nom(s)}</td>
                  <td>
                    <Cours date={s.course1_date} mode={s.course1_mode} />
                  </td>
                  <td>
                    <Cours date={s.course2_date} mode={s.course2_mode} />
                  </td>
                  <td>{age(s)}</td>
                  <td>{dateHeure(s.created_at)}</td>
                  <td className="essais__commentaire">{s.comment || '—'}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn--secondary"
                      disabled={!!(s.course1_date && s.course2_date)}
                      onClick={(e) => {
                        e.stopPropagation()
                        coursAujourdhui(s)
                      }}
                    >
                      + Cours aujourd'hui
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {liste && liste.length > 0 && (
        <>
          <p className="essais__legende">
            <span className="essais__nom--jour">Vert</span> : 1er cours aujourd'hui ·{' '}
            <span className="essais__nom--passe">Orange</span> : un cours déjà fait ·{' '}
            <span className="essais__nom--fini">Rouge</span> : les {MAX_COURS} cours faits
          </p>
          <p className="muted">Un inscrit est supprimé tout seul un an après son dernier cours ou son inscription.</p>
        </>
      )}
      {bandeau}
    </div>
  )
}

function Fiche({ ecoleId, id, onRetour, onChange, onCours, onSupprimer, liste }) {
  const [f, setF] = useState(null)
  const [erreur, setErreur] = useState('')
  const [commentaire, setCommentaire] = useState('')
  const [modifier, setModifier] = useState(false)
  const [signature, setSignature] = useState(false)
  const actuel = liste?.find((s) => s.id === id)

  useEffect(() => {
    api.fiche(ecoleId, id).then(
      (x) => {
        setF(x)
        setCommentaire(x.comment)
      },
      (e) => setErreur(e.message),
    )
  }, [ecoleId, id])

  // Les cours ajoutés depuis la liste arrivent par `liste`.
  const s = f && actuel ? { ...f, ...actuel } : f

  async function enregistrerCommentaire() {
    try {
      const maj = await api.modifier(ecoleId, id, { comment: commentaire })
      onChange(maj)
      setF((x) => ({ ...x, ...maj }))
    } catch (e) {
      setErreur(e.message)
    }
  }

  return (
    <div className="admin-panel essais">
      <div className="essais__retour">
        <button type="button" className="icon-btn" onClick={onRetour} aria-label="Retour">
          ←
        </button>
        <h2>{s ? nom(s) : '…'}</h2>
        {s && (
          <button type="button" className="btn btn--secondary" onClick={() => setModifier(true)}>
            Modifier
          </button>
        )}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {s && (
        <>
          <section className="essais__bloc">
            <h3>Cours d'essai</h3>
            <dl className="essais__dl">
              <dt>1er cours</dt>
              <dd>{s.course1_date ? `${dateCourte(s.course1_date)} (${mode(s.course1_mode)})` : '—'}</dd>
              <dt>2e cours</dt>
              <dd>{s.course2_date ? `${dateCourte(s.course2_date)} (${mode(s.course2_mode)})` : '—'}</dd>
            </dl>
            <button
              type="button"
              className="btn btn--secondary"
              disabled={!!(s.course1_date && s.course2_date)}
              onClick={() => onCours(s)}
            >
              + Cours aujourd'hui
            </button>
          </section>
          <section className="essais__bloc">
            <h3>Inscription</h3>
            <dl className="essais__dl">
              <dt>Inscrit</dt>
              <dd>en ligne le {dateHeure(s.created_at)}</dd>
              <dt>Âge</dt>
              <dd>{age(s)}</dd>
              {s.parent_name && (
                <>
                  <dt>Parent</dt>
                  <dd>{s.parent_name}</dd>
                </>
              )}
              <dt>E-mail</dt>
              <dd>{s.email}</dd>
              <dt>Téléphone</dt>
              <dd>{s.phone || '—'}</dd>
              {s.family.length > 0 && (
                <>
                  <dt>Même demande que</dt>
                  <dd>{s.family.join(', ')}</dd>
                </>
              )}
            </dl>
          </section>
          <section className="essais__bloc">
            <h3>Documents</h3>
            <button type="button" className="btn btn--secondary" onClick={() => setSignature(true)}>
              Signature et décharge
            </button>
            <p className="muted">
              Certificat médical fourni le {dateHeure(s.certificate_at)}. Il n'est pas gardé dans l'appli : il est joint au
              mail de confirmation, dont une copie est arrivée sur l'adresse du club.
            </p>
          </section>
          <section className="essais__bloc">
            <h3>Commentaire</h3>
            <textarea
              id="essais-commentaire"
              className="essais__champ"
              rows={3}
              placeholder="Ajouter un commentaire…"
              value={commentaire}
              onChange={(e) => setCommentaire(e.target.value)}
            />
            <button type="button" className="btn btn--secondary" disabled={commentaire === s.comment} onClick={enregistrerCommentaire}>
              Enregistrer le commentaire
            </button>
          </section>
          <section className="essais__bloc">
            <button type="button" className="btn btn--danger" onClick={() => onSupprimer(s)}>
              Supprimer {nom(s)}
            </button>
          </section>
          {modifier && (
            <Modifier
              s={s}
              onClose={() => setModifier(false)}
              onValider={async (champs) => {
                const maj = await api.modifier(ecoleId, id, champs)
                onChange(maj)
                setF((x) => ({ ...x, ...maj }))
                setModifier(false)
              }}
            />
          )}
          {signature && (
            <Modal title="Signature et décharge" onClose={() => setSignature(false)}>
              {s.signatures.map((sig, i) => (
                <div key={i} className="essais__signature">
                  <p>
                    Signé par {sig.signer_name} le {dateHeure(sig.created_at)}
                    {sig.children.length > 0 && `, ce qui vaut autorisation parentale pour ${sig.children.join(', ')}`}.
                  </p>
                  <img src={sig.png} alt={`Signature de ${sig.signer_name}`} />
                </div>
              ))}
              <p className="muted">Décharge acceptée, version {s.terms_number} du texte :</p>
              <p>{s.waiver}</p>
            </Modal>
          )}
        </>
      )}
    </div>
  )
}

function Modifier({ s, onClose, onValider }) {
  const [champs, setChamps] = useState({
    first_name: s.first_name,
    last_name: s.last_name,
    age: s.age ?? '',
    email: s.email,
    phone: s.phone ?? '',
    parent_name: s.parent_name ?? '',
    course1_date: s.course1_date ?? '',
    course2_date: s.course2_date ?? '',
  })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const champ = (cle, libelle, type = 'text') => (
    <label className="essais__label" htmlFor={`essais-${cle}`}>
      {libelle}
      <input
        id={`essais-${cle}`}
        className="essais__champ"
        type={type}
        value={champs[cle]}
        onChange={(e) => setChamps((c) => ({ ...c, [cle]: e.target.value }))}
      />
    </label>
  )

  async function valider() {
    setEnCours(true)
    setErreur('')
    try {
      await onValider({
        ...champs,
        age: champs.age === '' ? null : Number(champs.age),
        course1_date: champs.course1_date || null,
        course2_date: champs.course2_date || null,
      })
    } catch (e) {
      setErreur(e.message)
      setEnCours(false)
    }
  }

  return (
    <Modal
      title={`Modifier ${nom(s)}`}
      onClose={onClose}
      footer={
        <div className="essais__pied">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Annuler
          </button>
          <button type="button" className="btn btn--primary" onClick={valider} disabled={enCours}>
            Enregistrer
          </button>
        </div>
      }
    >
      {champ('first_name', 'Prénom')}
      {champ('last_name', 'Nom')}
      {champ('age', 'Âge (vide pour un majeur)', 'number')}
      {champ('email', 'E-mail', 'email')}
      {champ('phone', 'Téléphone', 'tel')}
      {champ('parent_name', 'Parent')}
      {champ('course1_date', '1er cours', 'date')}
      {champ('course2_date', '2e cours', 'date')}
      <p className="muted">Deux cours au plus. Effacer une date retire le cours.</p>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Une liste de lignes modifiables (règles, horaires, salles, contacts).
function Lignes({ lignes, vide, colonnes, onChange, ajouter }) {
  return (
    <>
      {lignes.map((l, i) => (
        <div key={i} className="essais__ligne-edit">
          {colonnes.map(([cle, libelle]) => (
            <input
              key={cle}
              id={`essais-${ajouter}-${i}-${cle}`}
              className="essais__champ"
              placeholder={libelle}
              aria-label={libelle}
              value={cle ? l[cle] ?? '' : l}
              onChange={(e) => onChange(lignes.map((x, j) => (j === i ? (cle ? { ...x, [cle]: e.target.value } : e.target.value) : x)))}
            />
          ))}
          <button type="button" className="icon-btn" aria-label="Retirer la ligne" onClick={() => onChange(lignes.filter((_, j) => j !== i))}>
            ✕
          </button>
        </div>
      ))}
      <button type="button" className="btn btn--secondary" onClick={() => onChange([...lignes, vide])}>
        + {ajouter}
      </button>
    </>
  )
}

function PageEssai({ ecoleId, onRetour, onCopier, onEnregistre }) {
  const [r, setR] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    api.reglages(ecoleId).then(setR, (e) => setErreur(e.message))
  }, [ecoleId])

  const maj = (cle) => (valeur) => setR((x) => ({ ...x, [cle]: valeur }))
  const texte = (cle, libelle, lignes = 0) => (
    <label className="essais__label" htmlFor={`essais-r-${cle}`}>
      {libelle}
      {lignes ? (
        <textarea id={`essais-r-${cle}`} className="essais__champ" rows={lignes} value={r[cle]} onChange={(e) => maj(cle)(e.target.value)} />
      ) : (
        <input id={`essais-r-${cle}`} className="essais__champ" value={r[cle]} onChange={(e) => maj(cle)(e.target.value)} />
      )}
    </label>
  )

  async function enregistrer() {
    setEnCours(true)
    setErreur('')
    try {
      setR(await api.enregistrerReglages(ecoleId, { ...r, min_age: Number(r.min_age) }))
      onEnregistre()
      onRetour()
    } catch (e) {
      setErreur(e.message)
    }
    setEnCours(false)
  }

  return (
    <div className="admin-panel essais">
      <div className="essais__retour">
        <button type="button" className="icon-btn" onClick={onRetour} aria-label="Retour">
          ←
        </button>
        <h2>Page d'essai</h2>
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {r && (
        <>
          <p className="muted">Tout ce que voit la personne qui s'inscrit, et le mail qu'elle reçoit.</p>
          <section className="essais__bloc">
            <h3>Lien de la page</h3>
            <p className="essais__lien">{r.link}</p>
            <div className="essais__boutons">
              <button type="button" className="btn btn--secondary" onClick={onCopier}>
                Copier le lien
              </button>
              <a className="btn btn--secondary" href={r.link} target="_blank" rel="noreferrer">
                Voir la page
              </a>
            </div>
          </section>
          <details className="essais__volet" open>
            <summary>Présentation</summary>
            {texte('title', 'Titre')}
            {texte('subtitle', 'Sous-titre')}
            {texte('intro', "Texte d'accueil", 4)}
          </details>
          <details className="essais__volet">
            <summary>Modalités</summary>
            <Lignes lignes={r.rules} vide="" colonnes={[['', 'Une règle']]} onChange={maj('rules')} ajouter="Ajouter une ligne" />
            <label className="essais__label" htmlFor="essais-r-min_age">
              Âge minimum
              <input id="essais-r-min_age" className="essais__champ essais__champ--court" type="number" min="3" max="17" value={r.min_age} onChange={(e) => maj('min_age')(e.target.value)} />
            </label>
          </details>
          <details className="essais__volet">
            <summary>Horaires d'entraînement</summary>
            <Lignes
              lignes={r.schedule}
              vide={{ day: '', time: '', course: '', place: '' }}
              colonnes={[['day', 'Jour'], ['time', 'Heure'], ['course', 'Cours'], ['place', 'Salle']]}
              onChange={maj('schedule')}
              ajouter="Ajouter un horaire"
            />
          </details>
          <details className="essais__volet">
            <summary>Salles</summary>
            <Lignes lignes={r.places} vide={{ name: '', address: '' }} colonnes={[['name', 'Nom'], ['address', 'Adresse']]} onChange={maj('places')} ajouter="Ajouter une salle" />
            <p className="muted">Le bouton « Voir sur la carte » est fait à partir de l'adresse.</p>
          </details>
          <details className="essais__volet">
            <summary>Contacts téléphone</summary>
            <Lignes lignes={r.contacts} vide={{ name: '', phone: '' }} colonnes={[['name', 'Prénom'], ['phone', 'Numéro']]} onChange={maj('contacts')} ajouter="Ajouter un contact" />
          </details>
          <details className="essais__volet">
            <summary>Certificat, décharge et autorisation parentale</summary>
            {texte('certificate_hint', 'Consigne pour le certificat médical')}
            {texte('waiver', 'Décharge de responsabilité', 7)}
            {texte('parental_consent', 'Autorisation parentale (au-dessus de la signature du parent)', 6)}
            <p className="muted">
              [élève], [parent] et [club] sont remplacés par les vrais noms. Les inscriptions déjà faites gardent le texte
              qu'elles ont accepté (version {r.terms_number} aujourd'hui).
            </p>
          </details>
          <button type="button" className="btn btn--primary btn--block essais__enregistrer" onClick={enregistrer} disabled={enCours}>
            Enregistrer
          </button>
        </>
      )}
    </div>
  )
}
