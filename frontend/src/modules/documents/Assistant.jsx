import { useEffect, useRef, useState } from 'react'
import { poserQuestion } from '../../api/assistant.js'
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

const dollars = (n) => `${(n ?? 0).toFixed(3).replace('.', ',')} $`

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

export default function Assistant({ orgId, contexte, onClose, onFaire }) {
  const [echanges, setEchanges] = useState([]) // { role, texte, actions?, etat? }
  const [conversationId, setConversationId] = useState(null)
  const [saisie, setSaisie] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [activite, setActivite] = useState('')
  const [cout, setCout] = useState(0)
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

  async function envoyer(texte) {
    const question = texte.trim()
    if (!question || enCours) return
    setSaisie('')
    setEnCours(true)
    setActivite('')
    setEchanges((l) => [...l, { role: 'user', texte: question }, { role: 'assistant', texte: '', actions: [] }])
    const actions = issues.current
    issues.current = []
    try {
      await poserQuestion(orgId, { conversationId, texte: question, contexte: { ...contexte, actions }, modele }, (e) => {
        if (e.type === 'conversation') setConversationId(e.id)
        else if (e.type === 'texte') {
          setActivite('')
          majDernier((m) => ({ ...m, texte: m.texte + e.texte }))
        } else if (e.type === 'outil') setActivite(EN_TRAIN_DE[e.nom] ?? 'Je prépare une proposition…')
        else if (e.type === 'action') majDernier((m) => ({ ...m, actions: [...m.actions, { ...e, etat: 'proposee' }] }))
        else if (e.type === 'fin') {
          setCout(e.cout_total_usd)
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
    <aside className="dx-chat" aria-label="Assistant">
      <div className="dx-chat__haut">
        <span className="dx-chat__titre">
          <BubbleIcon /> Assistant
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
          title="Coût et modèle"
        >
          {dollars(cout)}
        </button>
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Fermer l’assistant">
          ✕
        </button>
      </div>

      {panneauCout && (
        <div className="dx-chat__panneau">
          <h3>Coût de cette conversation : {dollars(cout)}</h3>
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
                    <td>{dollars(t.cout_usd)}</td>
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
                <small>{m.prix} $ par million de jetons (entrée / sortie)</small>
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

      <form
        className="dx-chat__saisie"
        onSubmit={(e) => {
          e.preventDefault()
          envoyer(saisie)
        }}
      >
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
        <button type="submit" className="dx-btn dx-btn--small" disabled={enCours || !saisie.trim()}>
          Envoyer
        </button>
      </form>
    </aside>
  )
}
