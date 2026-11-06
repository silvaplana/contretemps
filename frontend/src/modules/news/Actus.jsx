import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from './api.js'
import './news.css'

// Actualités (spec/modules/actualites.md, maquette validée
// spec/maquettes/actualites.html). Tout le monde lit les actus ; qui a le
// droit 🔒 « Publier les actualités » a deux onglets, Atelier et Aperçu.
// Un éditeur ouvert remplace l'écran, avec la flèche de retour.

const ANNULER_MS = 10000
const NIVEAUX = [
  { cle: 'important', libelle: 'Important', aide: 'En haut des actus, en rouge, jusqu’à la date choisie. Pour ce qui ne doit pas être manqué.' },
  { cle: 'normal', libelle: 'Normal', aide: 'Une grande carte.' },
  { cle: 'brief', libelle: 'Brève', aide: 'Une ligne. Pour les petites infos.' },
]
const LIBELLE = Object.fromEntries(NIVEAUX.map((n) => [n.cle, n.libelle]))

const jour = (d) => d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
function dansJours(n) {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return iso(d)
}

// « Aujourd'hui », « Cette semaine », « Plus tôt » (§3.2).
function periode(date) {
  const debut = new Date()
  debut.setHours(0, 0, 0, 0)
  if (date >= debut) return 'Aujourd’hui'
  debut.setDate(debut.getDate() - 6)
  return date >= debut ? 'Cette semaine' : 'Plus tôt'
}

function Alerte() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l10 18H2z" />
      <path d="M12 10v5M12 18v.5" />
    </svg>
  )
}

export function CarteActu({ actu }) {
  const signature = (
    <div className="actu__meta">
      <span>
        <b>{actu.auteur}</b>
        {actu.auteur ? ' · ' : ''}
        {jour(actu.publieeLe ?? new Date())}
      </span>
      {actu.nouveau && <span className="actu__nouveau">Nouveau</span>}
    </div>
  )
  if (actu.niveau === 'brief') {
    return (
      <article className="actu actu--breve">
        <span className="actu__point" aria-hidden="true" />
        <div>
          <p className="actu__texte">{actu.texte || '…'}</p>
          {signature}
        </div>
      </article>
    )
  }
  if (actu.niveau === 'important' && actu.enHaut) {
    return (
      <article className="actu actu--important">
        <div className="actu__drapeau">
          <Alerte />
          Important
        </div>
        <p className="actu__texte">{actu.texte || '…'}</p>
        {signature}
      </article>
    )
  }
  return (
    <article className="actu actu--normale">
      <p className="actu__texte">{actu.texte || '…'}</p>
      {signature}
    </article>
  )
}

function Fil({ actus }) {
  if (!actus.length) return <p className="actus__vide">Pas encore d’actu.</p>
  const enHaut = actus.filter((a) => a.enHaut)
  const autres = actus.filter((a) => !a.enHaut)
  const periodes = autres.map((a) => periode(a.publieeLe))
  return (
    <div className="actus__fil">
      {enHaut.map((a) => (
        <CarteActu key={a.id} actu={a} />
      ))}
      {autres.map((a, i) => {
        const titre = periodes[i] !== periodes[i - 1] ? periodes[i] : null
        return (
          <div key={a.id} className="actus__groupe">
            {titre && <div className="actus__periode">{titre}</div>}
            <CarteActu actu={a} />
          </div>
        )
      })}
      <p className="actus__fin">C’est tout pour le moment.</p>
    </div>
  )
}

function Atelier({ actus, ouvrir, ouverture, changerOuverture }) {
  return (
    <div className="atelier">
      {actus.map((a) => (
        <button key={a.id} type="button" className="atelier__ligne" onClick={() => ouvrir(a)}>
          <span className={`atelier__niveau atelier__niveau--${a.niveau}`} aria-hidden="true" />
          <span className="atelier__corps">
            <span className="atelier__texte">{a.texte}</span>
            <span className="actu__meta">
              <span className={`atelier__etat ${a.publieeLe ? 'is-publiee' : ''}`}>{a.publieeLe ? 'Publiée' : 'Brouillon'}</span>
              <span>
                {LIBELLE[a.niveau]} · {jour(a.publieeLe ?? a.modifieeLe)}
              </span>
            </span>
          </span>
        </button>
      ))}
      <div className="atelier__section">Options</div>
      <div className="atelier__option">
        <span>Ouvrir l’appli sur les actus</span>
        <button
          type="button"
          role="switch"
          aria-checked={ouverture}
          aria-label="Ouvrir l’appli sur les actus"
          className="actus__interrupteur"
          onClick={() => changerOuverture(!ouverture)}
        />
      </div>
    </div>
  )
}

function Editeur({ actu, auteur, onRetour, onEnregistrer, onSupprimer }) {
  const [brouillon, setBrouillon] = useState(actu)
  const [envoi, setEnvoi] = useState(false)
  const changer = (champs) => setBrouillon((b) => ({ ...b, ...champs }))
  const choisirNiveau = (niveau) =>
    changer({
      niveau,
      // Nouvelle actu : la notification suit le niveau (§4.2).
      ...(actu.id ? {} : { notifier: niveau === 'important' }),
      enHautJusquau: brouillon.enHautJusquau ?? dansJours(7),
    })
  const vide = !brouillon.texte.trim()
  const publiee = Boolean(actu.publieeLe)
  const aide = NIVEAUX.find((n) => n.cle === brouillon.niveau).aide

  async function envoyer(publier) {
    setEnvoi(true)
    try {
      await onEnregistrer({ ...brouillon, publier })
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div className="actus actus--editeur">
      <div className="actus__entete">
        <button type="button" className="actus__retour" aria-label="Retour" onClick={onRetour}>
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M19 12H5M11 18l-6-6 6-6" />
          </svg>
        </button>
        <strong>{actu.id ? 'Modifier l’actu' : 'Nouvelle actu'}</strong>
      </div>
      <div className="editeur">
        <div className="editeur__niveaux" role="group" aria-label="Niveau">
          {NIVEAUX.map((n) => (
            <button
              key={n.cle}
              type="button"
              className={`editeur__niveau editeur__niveau--${n.cle}`}
              aria-pressed={brouillon.niveau === n.cle}
              onClick={() => choisirNiveau(n.cle)}
            >
              {n.libelle}
            </button>
          ))}
        </div>
        <p className="editeur__aide">{aide}</p>
        <textarea
          id="actu-texte"
          className="editeur__texte"
          aria-label="Texte de l’actu"
          placeholder="Écrivez l’actu…"
          value={brouillon.texte}
          onChange={(e) => changer({ texte: e.target.value })}
        />
        {brouillon.niveau === 'important' && (
          <label className="editeur__ligne" htmlFor="actu-en-haut">
            <span>En haut jusqu’au</span>
            <input
              id="actu-en-haut"
              type="date"
              min={iso(new Date())}
              value={brouillon.enHautJusquau ?? dansJours(7)}
              onChange={(e) => changer({ enHautJusquau: e.target.value || dansJours(7) })}
            />
          </label>
        )}
        <div className="atelier__option">
          <span>Envoyer une notification</span>
          <button
            type="button"
            role="switch"
            aria-checked={brouillon.notifier}
            aria-label="Envoyer une notification"
            className="actus__interrupteur"
            onClick={() => changer({ notifier: !brouillon.notifier })}
          />
        </div>
        <div className="actus__periode">Ce que verront les autres</div>
        <div className="editeur__apercu">
          <CarteActu
            actu={{
              ...brouillon,
              enHaut: brouillon.niveau === 'important',
              auteur: actu.auteur || auteur,
              publieeLe: actu.publieeLe,
              nouveau: true,
            }}
          />
        </div>
        {actu.id && (
          <button type="button" className="editeur__supprimer" onClick={() => onSupprimer(actu)}>
            Supprimer cette actu
          </button>
        )}
      </div>
      <div className="actus__barre">
        <button type="button" className="btn btn--secondary actus__brouillon" disabled={vide || envoi} onClick={() => envoyer(false)}>
          Brouillon
        </button>
        <button type="button" className="btn btn--primary actus__principal" disabled={vide || envoi} onClick={() => envoyer(true)}>
          {publiee ? 'Enregistrer' : 'Publier'}
        </button>
      </div>
    </div>
  )
}

export default function Actus({ ecoleId, prenom }) {
  const [fil, setFil] = useState(null) // { peutPublier, actus }
  const [atelier, setAtelier] = useState([])
  const [onglet, setOnglet] = useState('apercu')
  const [ouverture, setOuverture] = useState(true)
  const [edite, setEdite] = useState(null) // l'actu ouverte dans l'éditeur
  const [caches, setCaches] = useState(new Set()) // supprimées, Annuler possible
  const [toast, setToast] = useState(null) // { texte, annuler }
  const [erreur, setErreur] = useState('')
  const minuteur = useRef(null)

  const charger = useCallback(async () => {
    try {
      const f = await api.lireActus(ecoleId)
      setFil(f)
      if (f.peutPublier) {
        const [a, o] = await Promise.all([api.lireAtelier(ecoleId), api.ouvrirSurLesActus(ecoleId)])
        setAtelier(a)
        setOuverture(o)
      }
      setErreur('')
    } catch (e) {
      setErreur(e.message)
    }
  }, [ecoleId])

  useEffect(() => {
    charger()
  }, [charger])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  const montrer = useCallback((texte, annuler) => {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), annuler ? ANNULER_MS : 3000)
  }, [])

  async function enregistrer(brouillon) {
    try {
      const actu = await api.enregistrer(ecoleId, brouillon)
      const vientDePublier = brouillon.publier && !edite.publieeLe
      setEdite(null)
      await charger()
      if (vientDePublier) {
        setOnglet('apercu')
        montrer('Actu publiée', async () => {
          await api.depublier(ecoleId, actu.id)
          charger()
        })
      } else {
        montrer(brouillon.publier ? 'Actu enregistrée' : 'Gardée en brouillon')
      }
    } catch (e) {
      montrer(e.message)
    }
  }

  // Supprimer : l'actu disparaît tout de suite et part vraiment au bout de
  // 10 s, comme dans Sparring.
  function supprimer(actu) {
    setEdite(null)
    setCaches((c) => new Set([...c, actu.id]))
    const retard = setTimeout(() => {
      api.supprimer(ecoleId, actu.id).then(charger, (e) => montrer(e.message))
    }, ANNULER_MS)
    montrer('Actu supprimée', () => {
      clearTimeout(retard)
      setCaches((c) => {
        const n = new Set(c)
        n.delete(actu.id)
        return n
      })
    })
  }

  async function changerOuverture(valeur) {
    setOuverture(valeur)
    try {
      await api.changerOuverture(ecoleId, valeur)
      montrer(valeur ? 'L’appli s’ouvrira sur les actus' : 'L’appli s’ouvrira sur le dernier onglet')
    } catch (e) {
      setOuverture(!valeur)
      montrer(e.message)
    }
  }

  const toastEl = toast && (
    <div className={`actus__toast ${edite || onglet === 'atelier' ? 'actus__toast--haut' : ''}`} role="status">
      <span>{toast.texte}</span>
      {toast.annuler && (
        <button
          type="button"
          onClick={() => {
            clearTimeout(minuteur.current)
            setToast(null)
            toast.annuler()
          }}
        >
          Annuler
        </button>
      )}
    </div>
  )

  if (edite) {
    return (
      <>
        <Editeur actu={edite} auteur={prenom} onRetour={() => setEdite(null)} onEnregistrer={enregistrer} onSupprimer={supprimer} />
        {toastEl}
      </>
    )
  }

  if (!fil) return <div className="actus">{erreur && <p className="actus__vide">{erreur}</p>}</div>
  const visibles = (liste) => liste.filter((a) => !caches.has(a.id))
  const vueAtelier = fil.peutPublier && onglet === 'atelier'

  return (
    <div className={`actus ${vueAtelier ? 'actus--avec-barre' : ''}`}>
      {fil.peutPublier && (
        <div className="actus__onglets" role="tablist">
          {[
            ['atelier', 'Atelier'],
            ['apercu', 'Aperçu'],
          ].map(([cle, libelle]) => (
            <button key={cle} type="button" role="tab" aria-selected={onglet === cle} onClick={() => setOnglet(cle)}>
              {libelle}
            </button>
          ))}
        </div>
      )}
      {vueAtelier ? (
        <Atelier actus={visibles(atelier)} ouvrir={setEdite} ouverture={ouverture} changerOuverture={changerOuverture} />
      ) : (
        <Fil actus={visibles(fil.actus)} />
      )}
      {vueAtelier && (
        <div className="actus__barre">
          <button
            type="button"
            className="btn btn--primary actus__principal"
            onClick={() => setEdite({ id: null, niveau: 'normal', texte: '', enHautJusquau: dansJours(7), notifier: false, publieeLe: null })}
          >
            Nouvelle actu
          </button>
        </div>
      )}
      {toastEl}
    </div>
  )
}
