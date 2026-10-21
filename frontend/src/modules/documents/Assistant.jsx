import { useEffect, useRef, useState } from 'react'
import { deposerPiece, faireModifications, poserQuestion } from '../../api/assistant.js'
import { enEuros } from '../../utils/euros.js'
import { dicteeDisponible, useDictee } from './Dictee.js'
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
  web_search: 'Je cherche sur internet…',
  web_fetch: 'Je lis la page sur internet…',
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
  lister_personnes: 'Je regarde les personnes…',
  infos_ecole: 'Je regarde les coordonnées de l’école…',
  lister_groupes: 'Je regarde les groupes…',
  proposer_modifications: 'Je prépare les changements…',
  modifier_fichier_appli: 'Je modifie le fichier…',
}

// Conversations gardées le temps de la visite, une par fichier de l'appli
// (`memoire`) : on la retrouve en rouvrant le fichier (un seul chat par
// fichier, fichier-de-base.md §2.1).
const conversationsGardees = new Map()

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

// Suggestions de l'accueil par défaut (Docs) ; chaque écran peut donner
// les siennes (`suggestions`), selon l'onglet ouvert.
const SUGGESTIONS = ['Que contient ce dossier ?', 'Quels sont les derniers fichiers modifiés ?']

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

export default function Assistant({
  orgId, contexte, onClose, onFaire, onFichier, onOuvrir, memoire, titre = 'Assistant', coutSaisonInitial = null,
  suggestions = SUGGESTIONS,
}) {
  const garde = memoire ? conversationsGardees.get(memoire) : null
  const [echanges, setEchanges] = useState(garde?.echanges ?? []) // { role, texte, actions?, etat? }
  const [conversationId, setConversationId] = useState(garde?.conversationId ?? null)
  const [saisie, setSaisie] = useState('')
  // Dictée (micro) : complète ce qui est déjà écrit.
  const saisieRef = useRef('')
  useEffect(() => {
    saisieRef.current = saisie
  }, [saisie])
  // ✕ pendant la dictée : on revient au texte d'avant, et ce qui arrive
  // encore de la reconnaissance est ignoré.
  const avantDictee = useRef('')
  const dicteeAnnulee = useRef(false)
  const dictee = useDictee(
    () => saisieRef.current,
    (texte) => {
      if (!dicteeAnnulee.current) setSaisie(texte)
    },
  )
  function dicter() {
    avantDictee.current = saisieRef.current
    dicteeAnnulee.current = false
    dictee.basculer()
  }
  function annulerDictee() {
    dicteeAnnulee.current = true
    dictee.arreter()
    setSaisie(avantDictee.current)
  }
  const [enCours, setEnCours] = useState(false)
  const [activite, setActivite] = useState('')
  const [cout, setCout] = useState(garde?.cout ?? 0)
  // Cumul « Chat documents » de l'école sur la saison (même relevé que
  // « Usage des ressources & IA »).
  const [coutSaison, setCoutSaison] = useState(coutSaisonInitial)
  const [tours, setTours] = useState(garde?.tours ?? []) // coût de chaque question
  useEffect(() => {
    if (memoire) conversationsGardees.set(memoire, { echanges, conversationId, cout, tours })
  }, [memoire, echanges, conversationId, cout, tours])
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
  const choixPhotos = useRef(null)
  const choixPhotoCamera = useRef(null)
  const [menuPlus, setMenuPlus] = useState(false)
  function choisir(ref) {
    setMenuPlus(false)
    ref.current?.click()
  }
  // Menu « + » ouvert : un appui ailleurs le ferme.
  useEffect(() => {
    if (!menuPlus) return
    const fermer = (e) => {
      if (!e.target.closest?.('.dx-chat__plus')) setMenuPlus(false)
    }
    document.addEventListener('pointerdown', fermer)
    return () => document.removeEventListener('pointerdown', fermer)
  }, [menuPlus])
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
      await poserQuestion(orgId, { conversationId, texte: question, contexte: { ...(typeof contexte === 'function' ? contexte() : contexte), actions }, modele, pieces: jointes.map((p) => p.id) }, (e) => {
        if (e.type === 'conversation') setConversationId(e.id)
        else if (e.type === 'texte') {
          setActivite('')
          majDernier((m) => ({ ...m, texte: m.texte + e.texte }))
        } else if (e.type === 'outil') setActivite(EN_TRAIN_DE[e.nom] ?? (e.nom?.includes('code_execution') ? EN_TRAIN_DE.code_execution : 'Je prépare une proposition…'))
        else if (e.type === 'action' && e.kind === 'fichier_modifie') {
          // Déjà enregistré par le serveur : l'écran du fichier le montre.
          onFichier?.(e)
          majDernier((m) => ({ ...m, actions: [...m.actions, { ...e, content: undefined }] }))
        } else if (e.type === 'action') majDernier((m) => ({ ...m, actions: [...m.actions, { ...e, etat: 'proposee' }] }))
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

  function majCarte(index, carte, champs) {
    setEchanges((liste) =>
      liste.map((m, i) =>
        i === index ? { ...m, actions: m.actions.map((a) => (a.id === carte.id ? { ...a, ...champs } : a)) } : m,
      ),
    )
  }

  // Carte récapitulative des modifications de données (cases à décocher).
  async function deciderModifications(index, carte, faire) {
    if (!faire) {
      majCarte(index, carte, { etat: 'annulee' })
      issues.current.push(`Annulé : ${carte.libelle} (rien n’a été modifié)`)
      return
    }
    const decochees = carte.decochees ?? []
    const indices = carte.lignes.map((_, i) => i).filter((i) => !decochees.includes(i))
    majCarte(index, carte, { etat: 'en_cours', erreur: null })
    try {
      const resultats = await faireModifications(orgId, carte.jeton, indices)
      majCarte(index, carte, { etat: 'faite', resultats })
      const faits = resultats.filter((r) => r.ok).map((r) => r.libelle)
      const echecs = resultats.filter((r) => !r.ok).map((r) => `${r.libelle} (${r.erreur})`)
      const ignores = decochees.map((i) => carte.lignes[i])
      if (faits.length) issues.current.push(`Fait : ${faits.join(' ; ')}`)
      if (echecs.length) issues.current.push(`Échec : ${echecs.join(' ; ')}`)
      if (ignores.length) issues.current.push(`Décoché par la personne, non fait : ${ignores.join(' ; ')}`)
      // Les autres écrans de l'appli rechargent leurs données.
      window.dispatchEvent(new Event('contretemps:donnees-modifiees'))
      // Un fichier créé (convocation, procès-verbal) s'ouvre au-dessus pour
      // être relu ; la question vient de l'appli, sans appel payant
      // (Seb, 21 octobre).
      const aOuvrir = resultats.find((r) => r.ok && r.ouvrir)?.ouvrir
      if (aOuvrir && onOuvrir) {
        onOuvrir(aOuvrir)
        setEchanges((l) => [
          ...l,
          {
            role: 'assistant',
            texte:
              `« ${aOuvrir.name} » est ouvert au-dessus, dans l’Aperçu. Le texte vous va ?\n\n` +
              'Touchez un texte de l’Aperçu pour le corriger directement, ou dites-moi ce qu’il faut changer. ' +
              'Quand il est bon, touchez **Valider** (ou dites-moi « valide ») : rien ne part avant.',
            actions: [],
          },
        ])
      }
    } catch (err) {
      majCarte(index, carte, { etat: 'proposee', erreur: err.message })
    }
  }

  async function annulerFichier(index, carte) {
    majCarte(index, carte, { etat: 'en_cours', erreur: null })
    try {
      await onFichier?.({ ...carte, annuler: true, avant: carte.avant })
      majCarte(index, carte, { etat: 'annulee' })
      issues.current.push(`Annulé par la personne, le fichier est revenu comme avant : ${carte.libelle}`)
    } catch (err) {
      majCarte(index, carte, { etat: 'faite', erreur: err.message })
    }
  }

  async function decider(index, carte, faire) {
    if (carte.kind === 'modifications') return deciderModifications(index, carte, faire)
    const changer = (etat, erreur) => majCarte(index, carte, { etat, erreur })
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
          <BubbleIcon /> <span className="dx-chat__titre-mot">{titre}</span>
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
          title={coutSaison != null ? 'Coût de cette conversation / de « Chat documents » sur la saison' : 'Coût de cette conversation'}
        >
          {euros(cout)}
          {coutSaison != null && ` / ${euros(coutSaison)}`}
        </button>
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Fermer l’assistant">
          ✕
        </button>
      </div>

      {panneauCout && (
        <div className="dx-chat__panneau">
          <h3>Coût de cette conversation : {euros(cout)}</h3>
          {coutSaison != null && <p className="dx-chat__etat">« Chat documents » sur la saison : {euros(coutSaison)}</p>}
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
            {suggestions.map((s) => (
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
                  {a.kind === 'modifications' && (
                    <ul className="dx-chat__modifs">
                      {a.lignes.map((ligne, j) => {
                        const resultat = a.resultats?.find((r) => r.index === j)
                        const coche = !(a.decochees ?? []).includes(j)
                        return (
                          <li key={j}>
                            {a.etat === 'proposee' || a.etat === 'en_cours' ? (
                              <label>
                                <input
                                  type="checkbox"
                                  checked={coche}
                                  disabled={a.etat === 'en_cours'}
                                  onChange={() =>
                                    majCarte(i, a, {
                                      decochees: coche ? [...(a.decochees ?? []), j] : (a.decochees ?? []).filter((x) => x !== j),
                                    })
                                  }
                                />
                                <span>{ligne}</span>
                              </label>
                            ) : (
                              <span className={resultat && !resultat.ok ? 'dx-error' : coche ? undefined : 'dx-chat__modif--non'}>
                                {resultat ? (resultat.ok ? '✓ ' : '✗ ') : '– '}
                                {ligne}
                                {resultat && !resultat.ok && ` : ${resultat.erreur}`}
                              </span>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                  {a.erreur && <p className="dx-error">{a.erreur}</p>}
                  {a.etat === 'proposee' || a.etat === 'en_cours' ? (
                    <div className="dx-chat__choix">
                      <button
                        type="button"
                        className="dx-btn dx-btn--small"
                        disabled={a.etat === 'en_cours' || (a.kind === 'modifications' && (a.decochees ?? []).length === a.lignes.length)}
                        onClick={() => decider(i, a, true)}
                      >
                        {a.kind === 'modifications'
                          ? a.etat === 'en_cours'
                            ? 'En cours…'
                            : a.lignes.length - (a.decochees ?? []).length === a.lignes.length
                              ? 'Tout faire'
                              : `Faire (${a.lignes.length - (a.decochees ?? []).length})`
                          : 'Faire'}
                      </button>
                      <button type="button" className="dx-btn dx-btn--small dx-btn--ghost" disabled={a.etat === 'en_cours'} onClick={() => decider(i, a, false)}>
                        Annuler
                      </button>
                    </div>
                  ) : a.kind === 'fichier_modifie' && a.etat === 'faite' && a.avant ? (
                    <div className="dx-chat__choix">
                      <span className="dx-chat__etat">✓ Fait</span>
                      <button type="button" className="dx-btn dx-btn--small dx-btn--ghost" onClick={() => annulerFichier(i, a)}>
                        Annuler
                      </button>
                    </div>
                  ) : (
                    <p className="dx-chat__etat">
                      {a.etat === 'annulee'
                        ? 'Annulé'
                        : a.resultats?.some((r) => !r.ok)
                          ? 'Fait en partie'
                          : '✓ Fait'}
                    </p>
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
      {/* Saisie façon appli Claude (demande de Seb, 2026-10-16) : « + » à
          gauche (photo, photos, fichiers), micro et flèche d'envoi à droite.
          Glisser-déposer et coller une capture marchent toujours. */}
      <form
        className="dx-chat__saisie"
        onSubmit={(e) => {
          e.preventDefault()
          dictee.arreter()
          envoyer(saisie)
        }}
      >
        <textarea
          ref={champ}
          rows={2}
          value={saisie}
          placeholder={dictee.ecoute ? 'Parlez, le texte s’écrit ici…' : 'Écrivez votre demande…'}
          onChange={(e) => setSaisie(e.target.value)}
          // Coller une capture d'écran (Ctrl+V) : jointe à la question.
          onPaste={(e) => {
            const images = [...(e.clipboardData?.files ?? [])]
            if (images.length) {
              e.preventDefault()
              joindre(images)
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              dictee.arreter()
              envoyer(saisie)
            }
          }}
        />
        {dictee.erreur && <p className="dx-chat__dictee-erreur">{dictee.erreur}</p>}
        {dictee.ecoute ? (
          // En écoute (Seb, 19 octobre, comme l'appli Claude) : ✕ annule, un
          // fil qui s'agite quand on entend une voix, ■ arrête, ↑ envoie.
          <div className="dx-chat__outils dx-chat__outils--ecoute">
            <button type="button" className="dx-chat__rond" aria-label="Annuler la dictée" onClick={annulerDictee}>
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
            <span className={`dx-fil${dictee.parle ? ' dx-fil--parle' : ''}`} aria-hidden="true">
              {Array.from({ length: 24 }, (_, i) => (
                <i key={i} />
              ))}
            </span>
            <button type="button" className="dx-chat__rond" aria-label="Arrêter la dictée" onClick={dictee.arreter}>
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <rect x="5" y="5" width="14" height="14" rx="2" fill="currentColor" />
              </svg>
            </button>
            <button
              type="submit"
              className="dx-chat__rond dx-chat__rond--envoyer"
              aria-label="Envoyer"
              disabled={enCours || piecesEnCours || (!saisie.trim() && piecesPretes.length === 0)}
            >
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 19V5M5 12l7-7 7 7" />
              </svg>
            </button>
          </div>
        ) : (
          <div className="dx-chat__outils">
            <div className="dx-chat__plus">
              <button
                type="button"
                className="dx-chat__rond"
                aria-label="Ajouter une photo ou un fichier"
                aria-expanded={menuPlus}
                onClick={() => setMenuPlus((v) => !v)}
              >
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>
              {menuPlus && (
                <div className="dx-chat__menu" role="menu">
                  <button type="button" role="menuitem" onClick={() => choisir(choixPhotoCamera)}>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
                      <circle cx="12" cy="13" r="3.5" />
                    </svg>
                    Prendre une photo
                  </button>
                  <button type="button" role="menuitem" onClick={() => choisir(choixPhotos)}>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="3" y="4" width="18" height="16" rx="2" />
                      <circle cx="9" cy="10" r="2" />
                      <path d="M21 16l-5-5-9 9" />
                    </svg>
                    Photos
                  </button>
                  <button type="button" role="menuitem" onClick={() => choisir(choixFichiers)}>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M14 3H6v18h12V7z" />
                      <path d="M14 3v4h4" />
                    </svg>
                    Fichiers
                  </button>
                </div>
              )}
              {[
                [choixPhotoCamera, { accept: 'image/*', capture: 'environment' }],
                [choixPhotos, { accept: 'image/*', multiple: true }],
                [choixFichiers, { multiple: true }],
              ].map(([ref, attributs], i) => (
                <input
                  key={i}
                  ref={ref}
                  type="file"
                  hidden
                  {...attributs}
                  onChange={(e) => {
                    joindre(e.target.files)
                    e.target.value = ''
                  }}
                />
              ))}
            </div>
            <div className="dx-chat__droite">
              {dicteeDisponible && (
                <button type="button" className="dx-chat__rond" aria-label="Dicter" title="Dicter" onClick={dicter}>
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="9" y="3" width="6" height="11" rx="3" />
                    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
                  </svg>
                </button>
              )}
              <button
                type="submit"
                className="dx-chat__rond dx-chat__rond--envoyer"
                aria-label="Envoyer"
                disabled={enCours || piecesEnCours || (!saisie.trim() && piecesPretes.length === 0)}
              >
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </form>
    </aside>
  )
}
