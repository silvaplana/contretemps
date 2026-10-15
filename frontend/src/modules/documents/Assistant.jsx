import { useEffect, useRef, useState } from 'react'
import { deposerPiece, poserQuestion } from '../../api/assistant.js'
import { enEuros } from '../../utils/euros.js'
import { BubbleIcon } from './icons.jsx'

// Conversation avec l'assistant (prototype, Seb 15 octobre ; spec
// documents.md §7.1 ter et plan, étape 5 bis). Sur ordinateur, un panneau à
// droite de l'explorateur ; sur téléphone, plein écran. L'assistant sait où
// l'on est (dossier ouvert, élément sélectionné), lit les fichiers, et
// propose des actions sous forme de cartes « Faire / Annuler » : c'est
// l'explorateur qui les exécute (`onFaire`), avec les droits habituels.

const EN_TRAIN_DE = {
  lister_dossier: 'Je regarde le dossier…',
  chercher: 'Je cherche…',
  fichiers_recents: 'Je regarde les derniers fichiers…',
  lire_fichier: 'Je lis le fichier…',
  copier_fichier_dans_l_ordinateur: 'Je prépare le fichier…',
  code_execution: 'Je travaille sur l’ordinateur…',
  resume_ecole: 'Je regarde les chiffres de l’école…',
  lister_cours: 'Je regarde les cours…',
  lister_eleves: 'Je regarde les élèves…',
  fiche_eleve: 'Je regarde la fiche de l’élève…',
  lister_professeurs: 'Je regarde les professeurs…',
  presences: 'Je regarde les présences…',
  heures_professeurs: 'Je regarde les heures des professeurs…',
  lister_choregraphies: 'Je regarde les chorégraphies…',
  lister_inscriptions_en_ligne: 'Je regarde les inscriptions…',
  lister_saisons: 'Je regarde les saisons…',
}

// Modèles au choix (panneau du coût, Seb 15 octobre), avec leur prix en
// dollars par million de jetons (entrée / sortie). Choix gardé sur l'appareil.
const MODELES = [
  { id: 'claude-opus-5-5', nom: 'Opus 5.5', detail: 'par défaut, très bon', prix: '4 / 20' },
  { id: 'claude-sonnet-5-5', nom: 'Sonnet 5.5', detail: 'rapide et bon', prix: '2 / 10' },
  { id: 'claude-haiku-5-5', nom: 'Haiku 5.5', detail: 'le plus rapide, le moins cher', prix: '0,10 / 0,50' },
  { id: 'claude-fable-5-1', nom: 'Fable 5.1', detail: 'le plus puissant, le plus cher', prix: '10 / 50' },
]
const CLE_MODELE = 'contretemps.assistant.modele'

function lireModele() {
  try {
    const m = localStorage.getItem(CLE_MODELE)
    return MODELES.some((x) => x.id === m) ? m : MODELES[0].id
  } catch {
    return MODELES[0].id
  }
}

// Coûts affichés en euros (taux BCE, voir utils/euros.js).
const euros = enEuros

const SUGGESTIONS = [
  'Que contient ce dossier ?',
  'Quels sont les derniers fichiers modifiés ?',
  'Résume le fichier sélectionné',
]

// Mise en forme légère des réponses : paragraphes, listes « - », **gras**.
function Texte({ texte }) {
  const blocs = texte.split(/\n{2,}/)
  const enLigne = (ligne, cle) =>
    ligne.split(/(\*\*[^*]+\*\*)/g).map((morceau, i) =>
      morceau.startsWith('**') && morceau.endsWith('**') ? <strong key={`${cle}-${i}`}>{morceau.slice(2, -2)}</strong> : morceau,
    )
  return blocs.map((bloc, i) => {
    const lignes = bloc.split('\n')
    if (lignes.every((l) => /^\s*[-•*] /.test(l))) {
      return (
        <ul key={i}>
          {lignes.map((l, j) => (
            <li key={j}>{enLigne(l.replace(/^\s*[-•*] /, ''), `${i}-${j}`)}</li>
          ))}
        </ul>
      )
    }
    return (
      <p key={i}>
        {lignes.map((l, j) => (
          <span key={j}>
            {j > 0 && <br />}
            {enLigne(l.replace(/^#+\s*/, ''), `${i}-${j}`)}
          </span>
        ))}
      </p>
    )
  })
}

export default function Assistant({ orgId, contexte, onClose, onFaire, coutSaisonInitial = null }) {
  const [echanges, setEchanges] = useState([]) // { role, texte, actions?, etat? }
  const [conversationId, setConversationId] = useState(null)
  const [saisie, setSaisie] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [activite, setActivite] = useState('')
  const [cout, setCout] = useState(0)
  // Cumul « Chat documents » de l'école sur la saison (même relevé que
  // « Usage des ressources & IA »).
  const [coutSaison, setCoutSaison] = useState(coutSaisonInitial)
  const [tours, setTours] = useState([]) // coût de chaque question
  const [panneauCout, setPanneauCout] = useState(false)
  const [modele, setModele] = useState(lireModele)

  function choisirModele(id) {
    setModele(id)
    try {
      localStorage.setItem(CLE_MODELE, id)
    } catch {
      // stockage indisponible : le choix vaut pour cette fois
    }
  }
  // Ce que la personne a fait des propositions, dit à l'assistant au
  // message suivant (« Fait : … », « Annulé : … »).
  const issues = useRef([])
  // Fichiers glissés (ou choisis au trombone), joints à la question suivante.
  const [pieces, setPieces] = useState([]) // { cle, nom, id?, erreur? }
  const [survol, setSurvol] = useState(false)
  const choixFichiers = useRef(null)
  const fil = useRef(null)
  const champ = useRef(null)

  useEffect(() => {
    fil.current?.scrollTo({ top: fil.current.scrollHeight })
  }, [echanges, activite])

  useEffect(() => {
    champ.current?.focus()
  }, [])

  function majDernier(maj) {
    setEchanges((liste) => {
      const copie = [...liste]
      copie[copie.length - 1] = maj(copie[copie.length - 1])
      return copie
    })
  }

  async function joindre(liste) {
    for (const fichier of [...liste].slice(0, 5)) {
      const cle = `${fichier.name}-${Date.now()}-${Math.random()}`
      setPieces((p) => [...p, { cle, nom: fichier.name }].slice(-5))
      deposerPiece(orgId, fichier).then(
        (x) => setPieces((p) => p.map((q) => (q.cle === cle ? { ...q, id: x.id } : q))),
        (e) => setPieces((p) => p.map((q) => (q.cle === cle ? { ...q, erreur: e.message } : q))),
      )
    }
  }

  // Éléments de Docs glissés sur l'assistant : joints par leur numéro
  // (le serveur les lit avec les droits de la personne).
  function joindreDocs(liste) {
    setPieces((p) => [...p, ...liste.map((x) => ({ cle: `doc-${x.id}-${Date.now()}`, nom: x.nom, id: `doc:${x.id}` }))].slice(-5))
  }

  // Au doigt, l'explorateur prévient par un événement (appui long, glisser,
  // lâcher sur l'assistant).
  useEffect(() => {
    const surJoindre = (e) => joindreDocs(e.detail)
    window.addEventListener('dx-joindre', surJoindre)
    return () => window.removeEventListener('dx-joindre', surJoindre)
  }, [])

  const piecesPretes = pieces.filter((p) => p.id)
  const piecesEnCours = pieces.some((p) => !p.id && !p.erreur)

  async function envoyer(texte) {
    const question = texte.trim() || (piecesPretes.length ? 'Voici le fichier joint.' : '')
    if (!question || enCours || piecesEnCours) return
    const jointes = piecesPretes
    setPieces([])
    setSaisie('')
    setEnCours(true)
    setActivite('')
    setEchanges((l) => [
      ...l,
      { role: 'user', texte: question, fichiers: jointes.map((p) => p.nom) },
      { role: 'assistant', texte: '', actions: [] },
    ])
    const actions = issues.current
    issues.current = []
    try {
      await poserQuestion(orgId, { conversationId, texte: question, contexte: { ...contexte, actions }, modele, pieces: jointes.map((p) => p.id) }, (e) => {
        if (e.type === 'conversation') setConversationId(e.id)
        else if (e.type === 'texte') {
          setActivite('')
          majDernier((m) => ({ ...m, texte: m.texte + e.texte }))
        } else if (e.type === 'outil') setActivite(EN_TRAIN_DE[e.nom] ?? 'Je prépare une proposition…')
        else if (e.type === 'action') majDernier((m) => ({ ...m, actions: [...m.actions, { ...e, etat: 'proposee' }] }))
        else if (e.type === 'fin') {
          setCout(e.cout_total_usd)
          if (e.cout_saison_usd != null) setCoutSaison(e.cout_saison_usd)
          setTours((t) => [...t, e.tour])
        }
        else if (e.type === 'erreur') majDernier((m) => ({ ...m, erreur: e.message }))
      })
    } catch (err) {
      majDernier((m) => ({ ...m, erreur: err.message }))
    } finally {
      setEnCours(false)
      setActivite('')
    }
  }

  async function decider(index, carte, faire) {
    const changer = (etat, erreur) =>
      setEchanges((liste) =>
        liste.map((m, i) =>
          i === index ? { ...m, actions: m.actions.map((a) => (a.id === carte.id ? { ...a, etat, erreur } : a)) } : m,
        ),
      )
    if (!faire) {
      changer('annulee')
      issues.current.push(`Annulé : ${carte.libelle}`)
      return
    }
    changer('en_cours')
    try {
      await onFaire(carte)
      changer('faite')
      issues.current.push(`Fait : ${carte.libelle}`)
    } catch (err) {
      changer('proposee', err.message)
      issues.current.push(`Échec de « ${carte.libelle} » : ${err.message}`)
    }
  }

  return (
    <aside
      className={`dx-chat${survol ? ' dx-chat--survol' : ''}`}
      aria-label="Assistant"
      // Glisser un fichier sur l'assistant : joint à la question suivante
      // (sans le ranger dans Docs : l'explorateur derrière n'est pas concerné).
      data-drop-folder="assistant"
      onDragOver={(e) => {
        const types = [...e.dataTransfer.types]
        if (!types.includes('Files') && !types.includes('application/x-dx-noms')) return
        e.preventDefault()
        e.stopPropagation()
        setSurvol(true)
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setSurvol(false)
      }}
      onDrop={(e) => {
        const docs = e.dataTransfer.getData('application/x-dx-noms')
        if (docs) {
          e.preventDefault()
          e.stopPropagation()
          setSurvol(false)
          try {
            joindreDocs(JSON.parse(docs))
          } catch {
            // données illisibles : rien à joindre
          }
          return
        }
        if (!e.dataTransfer.files?.length) return
        e.preventDefault()
        e.stopPropagation()
        setSurvol(false)
        joindre(e.dataTransfer.files)
      }}
    >
      <div className="dx-chat__haut">
        <span className="dx-chat__titre">
          <BubbleIcon /> <span className="dx-chat__titre-mot">Assistant</span>
        </span>
        {echanges.length > 0 && (
          <button
            type="button"
            className="dx-chat__nouvelle"
            disabled={enCours}
            onClick={() => {
              setEchanges([])
              setConversationId(null)
              setCout(0)
              setTours([])
              issues.current = []
            }}
          >
            Nouvelle
          </button>
        )}
        <button
          type="button"
          className="dx-chat__cout-bouton"
          onClick={() => setPanneauCout((o) => !o)}
          aria-expanded={panneauCout}
          title="Coût de cette conversation / de « Chat documents » sur la saison"
        >
          {euros(cout)} / {euros(coutSaison ?? cout)}
        </button>
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Fermer l’assistant">
          ✕
        </button>
      </div>

      {panneauCout && (
        <div className="dx-chat__panneau">
          <h3>Coût de cette conversation : {euros(cout)}</h3>
          <p className="dx-chat__etat">« Chat documents » sur la saison : {euros(coutSaison ?? cout)}</p>
          {tours.length === 0 ? (
            <p className="dx-chat__etat">Aucune demande pour l’instant.</p>
          ) : (
            <table className="dx-chat__tours">
              <thead>
                <tr>
                  <th>Demande</th>
                  <th>Modèle</th>
                  <th>Jetons</th>
                  <th>Coût</th>
                </tr>
              </thead>
              <tbody>
                {tours.map((t, i) => (
                  <tr key={i}>
                    <td title={t.question}>{t.question}</td>
                    <td>{t.modele}</td>
                    <td>
                      {t.jetons_entree.toLocaleString('fr-FR')} + {t.jetons_sortie.toLocaleString('fr-FR')}
                      {t.appels > 1 ? ` (${t.appels} appels)` : ''}
                    </td>
                    <td>{euros(t.cout_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <h3>Modèle utilisé</h3>
          {MODELES.map((m) => (
            <label key={m.id} className="dx-chat__modele">
              <input type="radio" name="modele" checked={modele === m.id} onChange={() => choisirModele(m.id)} />
              <span>
                <b>{m.nom}</b> · {m.detail}
                <small>{m.prix} $ par million de jetons (entrée / sortie), facturés en dollars</small>
              </span>
            </label>
          ))}
          <button type="button" className="dx-btn dx-btn--small" onClick={() => setPanneauCout(false)}>
            Fermer
          </button>
        </div>
      )}

      <div className="dx-chat__fil" ref={fil}>
        {echanges.length === 0 && (
          <div className="dx-chat__accueil">
            <p className="dx-chat__bonjour">Puis-je vous aider ?</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="dx-chat__suggestion" onClick={() => envoyer(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
        {echanges.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="dx-chat__moi">
              {m.fichiers?.length > 0 && <div className="dx-chat__joints">Joint : {m.fichiers.join(', ')}</div>}
              {m.texte}
            </div>
          ) : (
            <div key={i} className="dx-chat__lui">
              {m.texte && <Texte texte={m.texte} />}
              {m.actions?.map((a) => (
                <div key={a.id} className={`dx-chat__carte dx-chat__carte--${a.etat}`}>
                  <p>{a.libelle}</p>
                  {a.kind === 'creer_fichier_texte' && <pre className="dx-chat__apercu">{a.contenu}</pre>}
                  {a.erreur && <p className="dx-error">{a.erreur}</p>}
                  {a.etat === 'proposee' || a.etat === 'en_cours' ? (
                    <div className="dx-chat__choix">
                      <button type="button" className="dx-btn dx-btn--small" disabled={a.etat === 'en_cours'} onClick={() => decider(i, a, true)}>
                        Faire
                      </button>
                      <button type="button" className="dx-btn dx-btn--small dx-btn--ghost" disabled={a.etat === 'en_cours'} onClick={() => decider(i, a, false)}>
                        Annuler
                      </button>
                    </div>
                  ) : (
                    <p className="dx-chat__etat">{a.etat === 'faite' ? '✓ Fait' : 'Annulé'}</p>
                  )}
                </div>
              ))}
              {m.erreur && <p className="dx-error">{m.erreur}</p>}
              {i === echanges.length - 1 && enCours && (
                <p className="dx-chat__activite">{activite || (m.texte ? '' : 'Je réfléchis…')}</p>
              )}
            </div>
          ),
        )}
      </div>

      {pieces.length > 0 && (
        <div className="dx-chat__pieces">
          {pieces.map((p) => (
            <span key={p.cle} className={`dx-chat__piece${p.erreur ? ' dx-chat__piece--erreur' : ''}`} title={p.erreur || p.nom}>
              {p.erreur ? '! ' : p.id ? '' : '… '}
              {p.nom}
              <button type="button" aria-label={`Retirer ${p.nom}`} onClick={() => setPieces((l) => l.filter((q) => q.cle !== p.cle))}>
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
      <form
        className="dx-chat__saisie"
        onSubmit={(e) => {
          e.preventDefault()
          envoyer(saisie)
        }}
      >
        <button
          type="button"
          className="dx-chat__trombone"
          onClick={() => choixFichiers.current?.click()}
          aria-label="Joindre un fichier"
          title="Joindre un fichier (ou glissez-le ici)"
        >
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M20 11.5l-8.2 8.2a5 5 0 0 1-7.1-7.1l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4l7.8-7.8" />
          </svg>
        </button>
        <input
          ref={choixFichiers}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            joindre(e.target.files)
            e.target.value = ''
          }}
        />
        <textarea
          ref={champ}
          rows={2}
          value={saisie}
          placeholder="Écrivez votre demande…"
          onChange={(e) => setSaisie(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              envoyer(saisie)
            }
          }}
        />
        <button
          type="submit"
          className="dx-btn dx-btn--small"
          disabled={enCours || piecesEnCours || (!saisie.trim() && piecesPretes.length === 0)}
        >
          Envoyer
        </button>
      </form>
    </aside>
  )
}
