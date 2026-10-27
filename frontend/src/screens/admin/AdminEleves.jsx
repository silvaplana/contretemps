import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import * as champsApi from '../../api/champs.js'
import * as elevesApi from '../../api/eleves.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import MenuEntete from '../../components/MenuEntete.jsx'
import Modal from '../../components/Modal.jsx'
import { ordonner } from '../../data/colonnesEleves.js'
import { paiementLabels } from '../../data/paiement.js'
import { calculerAge } from '../../utils/age.js'
import { ouvrirInscriptionEleve } from '../../utils/inscriptionEleve.js'
import { correspond } from '../../utils/recherche.js'
import { texteReponse } from '../../utils/reponses.js'
import AjoutEleveOcr from './AjoutEleveOcr.jsx'
import ChampsMembres from './ChampsMembres.jsx'
import FicheEleve from './FicheEleve.jsx'
import { BoutonInviter, InviterTous, MessageAcces, StatutAcces, useAcces } from './AccesInvitation.jsx'
import IntegrerFichierElevesModal from './IntegrerFichierElevesModal.jsx'

const PAIEMENT_TONE = { en_cours: 'warning', paye: 'success' }

const DUREE_APPUI_LONG = 500 // ms

// Libellé affiché en titre de la popover "voir en entier / marquer en
// rouge" (appui long — voir ci-dessous), et texte complet par colonne pour
// cette même popover : utile quand une cellule est trop étroite pour tout
// montrer (ex. beaucoup de cours, adresse longue...).
const CHAMP_LABEL = {
  nom: 'Élève',
  cours: 'Cours suivis',
  paiement: 'Paiement',
  commentaire: 'Commentaire',
  age: 'Âge',
  contacts: 'Contacts',
  telephone: 'Téléphone',
  email: 'Email',
  certificat: 'Certificat médical',
}

// « Prénom Nom (Lien) », sans « (null) » ni parenthèses vides quand un
// champ manque (cas des contacts importés sans lien de parenté).
function nomContact(c) {
  const nom = [c.prenom, c.nom].filter(Boolean).join(' ')
  return c.lien ? `${nom} (${c.lien})` : nom
}

function valeurCellule(el, champ, cours) {
  switch (champ) {
    case 'nom':
      return `${el.prenom} ${el.nom}`
    case 'cours':
      return el.coursIds.map((cid) => cours.find((c) => c.id === cid)?.nom).filter(Boolean).join(', ')
    case 'paiement':
      return `${paiementLabels[el.statutPaiement]} — ${el.montantPaye}€ / ${el.montantTotalAnnee}€`
    case 'commentaire':
      return el.commentaireAdmin
    case 'age': {
      const age = calculerAge(el.dateNaissance)
      return age == null ? '' : `${age} ans`
    }
    case 'contacts':
      return el.contactsEleve
        .map((c) => [nomContact(c), c.telephone, c.email].filter(Boolean).join(' — '))
        .join('\n')
    case 'telephone':
      return el.telephone
    case 'email':
      return el.email
    case 'certificat':
      return el.certificatMedical ? 'Reçu' : 'Manquant'
    default:
      return ''
  }
}

// Onglet Admin > Élèves (voir spec/SPEC.md §5.1.2 et §6.4). Les champs les
// moins consultés au quotidien (contacts, santé) sont regroupés dans une
// modale par ligne plutôt qu'en colonnes, pour garder le tableau lisible.
//
// Données métier (nom, contacts, cours suivis...) via api/eleves.js (voir
// api/README.md) — `eleves`/`setEleves` viennent de App.jsx, mis à jour ici
// après chaque appel réussi. Le surlignage rouge (appui long) est gardé en
// base depuis le 2026-10-16 (`ligne_rouge`, `cellules_rouges` du profil) :
// tous les admins le voient, et l'assistant peut le poser.
export default function AdminEleves({ eleves, setEleves, cours, ecoleId }) {
  const [search, setSearch] = useState('')
  // Accès à l'appli (spec §2.2) : colonnes « Inviter » et « Statut ».
  const acces = useAcces(ecoleId)
  const [ocrOuvert, setOcrOuvert] = useState(false)
  const [champsOuverts, setChampsOuverts] = useState(false)
  // Colonnes du tableau (spec/core.md §4.3) : l'ordre et la case Afficher
  // réglés dans « Affichage dans Admin », et les champs de la fiche avec les
  // réponses de tous les élèves. Relus à la fermeture de « Champs ».
  const [reglage, setReglage] = useState({ colonnes: [], champs: [], reponses: {}, sousGroupes: {} })
  const relireColonnes = useCallback(async () => {
    try {
      const [colonnes, champs, reponses, choix] = await Promise.all([
        champsApi.colonnes(ecoleId),
        champsApi.lister(ecoleId),
        champsApi.toutesReponses(ecoleId),
        champsApi.groupes(ecoleId),
      ])
      const sousGroupes = Object.fromEntries(choix.parents.map((g) => [g.id, g.children]))
      setReglage({ colonnes, champs, reponses, sousGroupes })
    } catch {
      // Hors ligne : les colonnes d'origine restent affichées.
    }
  }, [ecoleId])
  useEffect(() => {
    relireColonnes()
  }, [relireColonnes])
  const { reponses, sousGroupes } = reglage
  const toutesColonnes = ordonner(reglage.colonnes, reglage.champs)
  const affichees = toutesColonnes.filter((c) => c.shown)

  // Un élève peut être ajouté depuis un autre onglet (« Inscription élève
  // (OCR) » ouvre le formulaire à part) : la liste est relue dès qu'on
  // revient sur l'appli, sans avoir à la recharger.
  const relireEleves = useCallback(() => {
    elevesApi.lister(ecoleId).then(setEleves).catch(() => {})
  }, [ecoleId, setEleves])

  useEffect(() => {
    let dernier = 0
    async function relire() {
      if (document.visibilityState !== 'visible' || Date.now() - dernier < 2000) return
      dernier = Date.now()
      try {
        setEleves(await elevesApi.lister(ecoleId))
      } catch {
        // Hors ligne : la liste affichée reste en place.
      }
    }
    document.addEventListener('visibilitychange', relire)
    window.addEventListener('focus', relire)
    return () => {
      document.removeEventListener('visibilitychange', relire)
      window.removeEventListener('focus', relire)
    }
  }, [ecoleId, setEleves])
  // Élève ajouté, supprimé, ou email changé : les statuts sont relus (un
  // email modifié rattache la fiche à une autre adresse, à inviter).
  const emails = eleves.map((el) => `${el.id}:${el.email ?? ''}`).join('|')
  useEffect(() => {
    acces.recharger()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [emails])
  // Fiche de l'élève (voir FicheEleve.jsx), ouverte d'un clic sur sa
  // ligne : le tableau n'est plus modifiable (demande du 2026-10-15).
  const [ficheId, setFicheId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [showImport, setShowImport] = useState(false)
  // Appui long sur une cellule (voir spec — trop petite pour tout montrer
  // parfois) : ouvre une popover avec la valeur complète + la possibilité
  // de marquer cette cellule, ou toute la ligne, en rouge.
  const [pressed, setPressed] = useState(null) // { eleveId, champ }
  const [copieOk, setCopieOk] = useState(false)
  const minuteurRef = useRef(null)
  const ignorerProchainClicRef = useRef(false)

  // Surlignage rouge — voir note en tête de fichier.
  function surlignageDe(eleveId) {
    const el = eleves.find((x) => x.id === eleveId)
    return { cellulesRouges: el?.cellules_rouges ?? [], ligneRouge: Boolean(el?.ligne_rouge) }
  }

  async function copierValeur(valeur) {
    try {
      await navigator.clipboard.writeText(valeur)
      setCopieOk(true)
      setTimeout(() => setCopieOk(false), 1500)
    } catch {
      // Presse-papier indisponible (contexte non sécurisé, permission
      // refusée...) — la valeur reste affichée dans la popover pour la
      // recopier à la main, ce n'est pas bloquant.
    }
  }

  function demarrerAppuiLong(eleveId, champ) {
    clearTimeout(minuteurRef.current)
    minuteurRef.current = setTimeout(() => {
      ignorerProchainClicRef.current = true
      // Un élément de la cellule a pu prendre le focus pendant l'appui :
      // on le lui retire, la popover passe devant.
      document.activeElement?.blur?.()
      setPressed({ eleveId, champ })
    }, DUREE_APPUI_LONG)
  }
  function annulerAppuiLong() {
    clearTimeout(minuteurRef.current)
  }
  // En capture (avant le onClick du bouton/lien à l'intérieur de la
  // cellule) : avale le clic qui suit un appui long, sinon la popover qui
  // vient de s'ouvrir se ferme aussitôt (le clic tombe sur son overlay).
  function avalerClicSiAppuiLong(e) {
    if (ignorerProchainClicRef.current) {
      e.preventDefault()
      e.stopPropagation()
      ignorerProchainClicRef.current = false
    }
  }

  function celluleProps(eleveId, champ) {
    return {
      onPointerDown: () => demarrerAppuiLong(eleveId, champ),
      onPointerUp: annulerAppuiLong,
      onPointerLeave: annulerAppuiLong,
      onPointerCancel: annulerAppuiLong,
      onContextMenu: (e) => e.preventDefault(),
      onClickCapture: avalerClicSiAppuiLong,
    }
  }

  // Tout de suite à l'écran, puis enregistré ; remis comme avant si l'appel échoue.
  async function changerRouge(eleveId, patch) {
    const avant = eleves.find((x) => x.id === eleveId)
    setEleves((list) => list.map((el) => (el.id === eleveId ? { ...el, ...patch } : el)))
    try {
      remplacer(await elevesApi.modifier(eleveId, patch))
    } catch {
      if (avant) remplacer(avant)
    }
  }

  function toggleCelluleRouge(eleveId, champ) {
    const { cellulesRouges } = surlignageDe(eleveId)
    const cellules = cellulesRouges.includes(champ) ? cellulesRouges.filter((c) => c !== champ) : [...cellulesRouges, champ]
    changerRouge(eleveId, { cellules_rouges: cellules })
  }

  function toggleLigneRouge(eleveId) {
    changerRouge(eleveId, { ligne_rouge: !surlignageDe(eleveId).ligneRouge })
  }

  const filtered = eleves.filter((el) => correspond(`${el.prenom} ${el.nom}`, search))

  // Remplace l'élève mis à jour (renvoyé par l'API) dans la liste locale.
  function remplacer(eleveMisAJour) {
    setEleves((list) => list.map((el) => (el.id === eleveMisAJour.id ? eleveMisAJour : el)))
  }


  async function remove(id) {
    if (!window.confirm('Supprimer cet élève ?')) return
    await elevesApi.supprimer(id)
    setEleves((list) => list.filter((el) => el.id !== id))
    setSurlignage((s) => {
      const { [id]: _retire, ...reste } = s
      return reste
    })
  }

  async function addEleve(nom, prenom) {
    const nouveau = await elevesApi.creer(ecoleId, { nom, prenom })
    // En dev, StrictMode appelle cet updater deux fois DE SUITE (la 2e
    // fois avec le résultat de la 1re en entrée, pas la liste d'avant) —
    // pour détecter justement ce genre de bug. `[...list, nouveau]` sans
    // garde ajouterait `nouveau` deux fois. Le test d'existence rend
    // l'updater idempotent, sûr à ré-appliquer sur son propre résultat.
    setEleves((list) => (list.some((el) => el.id === nouveau.id) ? list : [...list, nouveau]))
  }


  const eleveEnFiche = eleves.find((el) => el.id === ficheId)

  // Le tableau occupe exactement la hauteur restante de l'écran (demande du
  // 2026-10-15) : seul lui défile, la page reste en place et son en-tête de
  // colonnes ne passe plus sous la barre des onglets Admin.
  const boiteTableauRef = useRef(null)
  useEffect(() => {
    const boite = boiteTableauRef.current
    const page = boite?.closest('.app__content')
    if (!boite || !page) return undefined
    function ajuster() {
      const haut = boite.getBoundingClientRect().top - page.getBoundingClientRect().top + page.scrollTop
      boite.style.maxHeight = `${Math.max(240, page.clientHeight - haut - 16)}px`
    }
    ajuster()
    const observateur = new ResizeObserver(ajuster)
    observateur.observe(page)
    return () => observateur.disconnect()
  }, [])
  const eleveAppuye = pressed ? eleves.find((el) => el.id === pressed.eleveId) : null
  // Une colonne d'un champ de la fiche : son intitulé et la réponse en clair.
  const champAppuye = pressed ? toutesColonnes.find((c) => c.key === pressed.champ && c.champ)?.champ : null
  function valeurAppuyee() {
    if (!champAppuye) return valeurCellule(eleveAppuye, pressed.champ, cours)
    return texteReponse(champAppuye, reponses[eleveAppuye.id]?.[champAppuye.id], sousGroupes[champAppuye.group_id])
  }

  return (
    <div className="admin-panel admin-panel--eleves">
      {/* Menu ⋮ dans l'en-tête (demande du 2026-09-25). */}
      <MenuEntete
        label="Menu Élèves"
        actions={[
          {
            label: 'Inscription élève (OCR)',
            icon: 'camera',
            onClick: () => setOcrOuvert(true),
            groupeAvecSuivante: true,
          },
          { label: 'Inscription élève (web)', icon: 'users', onClick: ouvrirInscriptionEleve },
          // La fiche d'un membre (spec/core.md §4.3).
          { label: 'Champs', icon: 'edit', onClick: () => setChampsOuverts(true) },
        ]}
      />
      {champsOuverts && (
        <ChampsMembres
          ecoleId={ecoleId}
          onClose={() => {
            setChampsOuverts(false)
            relireColonnes()
            // « Synchroniser maintenant » (HelloAsso) a pu ajouter des fiches.
            relireEleves()
          }}
        />
      )}
      {ocrOuvert && (
        <AjoutEleveOcr ecoleId={ecoleId} onEleveAjoute={relireEleves} onClose={() => setOcrOuvert(false)} />
      )}
      <div className="search-bar">
        <Icon name="search" size={18} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher un élève par nom"
        />
      </div>
      <MessageAcces acces={acces} />

      <div className="table-scroll table-scroll--eleves" ref={boiteTableauRef}>
        <table className="data-table data-table--eleves">
          <thead>
            <tr>
              {affichees.map((c) => (
                <th key={c.key}>
                  {c.key === 'inviter' ? (
                    <InviterTous acces={acces} compteIds={filtered.map((el) => el.id)} />
                  ) : c.key === 'statut' ? (
                    'Statut'
                  ) : (
                    c.label
                  )}
                </th>
              ))}
              <th aria-label="Supprimer" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((el) => {
              const { cellulesRouges, ligneRouge } = surlignageDe(el.id)
              function classeCellule(champ) {
                return cellulesRouges.includes(champ) ? 'is-cellule-rouge' : ''
              }
              const cellules = {
                nom: (
                  <td className={`data-table__name ${classeCellule('nom')}`} {...celluleProps(el.id, 'nom')}>
                    <button type="button" className="cell-comment cell-comment--nom" onClick={() => setFicheId(el.id)}>
                      {el.prenom} {el.nom}
                    </button>
                  </td>
                ),
                cours: (
                  <td className={classeCellule('cours')} {...celluleProps(el.id, 'cours')}>
                    <button
                      type="button"
                      className="badge-list badge-list--button"
                      onClick={() => setFicheId(el.id)}
                    >
                      {el.coursIds.length === 0 && <span className="muted">—</span>}
                      {el.coursIds.map((cid) => (
                        <Badge key={cid}>{cours.find((c) => c.id === cid)?.nom}</Badge>
                      ))}
                    </button>
                  </td>
                ),
                paiement: (
                  <td className={classeCellule('paiement')} {...celluleProps(el.id, 'paiement')}>
                    <button
                      type="button"
                      className={`select-pill select-pill--${PAIEMENT_TONE[el.statutPaiement]}`}
                      onClick={() => setFicheId(el.id)}
                    >
                      {paiementLabels[el.statutPaiement]} — {el.montantPaye}€/{el.montantTotalAnnee}€
                    </button>
                  </td>
                ),
                commentaire: (
                  <td className={classeCellule('commentaire')} {...celluleProps(el.id, 'commentaire')}>
                    <button
                      type="button"
                      className="cell-comment"
                      onClick={() => setFicheId(el.id)}
                    >
                      {el.commentaireAdmin || <span className="muted">—</span>}
                    </button>
                  </td>
                ),
                age: (
                  <td className={classeCellule('age')} {...celluleProps(el.id, 'age')}>
                    {calculerAge(el.dateNaissance) ?? <span className="muted">—</span>}
                  </td>
                ),
                contacts: (
                  <td className={classeCellule('contacts')} {...celluleProps(el.id, 'contacts')}>
                    <button
                      type="button"
                      className="cell-comment"
                      onClick={() => setFicheId(el.id)}
                    >
                      {el.contactsEleve.length === 0 ? (
                        <span className="muted">—</span>
                      ) : el.contactsEleve.length === 1 ? (
                        nomContact(el.contactsEleve[0])
                      ) : (
                        `${el.contactsEleve.length} contacts`
                      )}
                    </button>
                  </td>
                ),
                telephone: (
                  <td className={classeCellule('telephone')} {...celluleProps(el.id, 'telephone')}>
                    <button type="button" className="cell-comment" onClick={() => setFicheId(el.id)}>
                      {el.telephone || <span className="muted">—</span>}
                    </button>
                  </td>
                ),
                email: (
                  <td className={classeCellule('email')} {...celluleProps(el.id, 'email')}>
                    <button type="button" className="cell-comment" onClick={() => setFicheId(el.id)}>
                      {el.email || <span className="muted">—</span>}
                    </button>
                  </td>
                ),
                certificat: (
                  <td className={classeCellule('certificat')} {...celluleProps(el.id, 'certificat')}>
                    <span className={`toggle-chip ${el.certificatMedical ? 'is-on' : ''}`}>
                      {el.certificatMedical ? 'Reçu' : 'Manquant'}
                    </span>
                  </td>
                ),
                inviter: (
                  <td>
                    <BoutonInviter acces={acces} compteId={el.id} prenom={el.prenom} />
                  </td>
                ),
                statut: (
                  <td>
                    <StatutAcces acces={acces} compteId={el.id} />
                  </td>
                ),
              }
              return (
                <tr key={el.id} className={ligneRouge ? 'is-ligne-rouge' : ''}>
                  {affichees.map((c) =>
                    c.champ ? (
                      <td key={c.key} className={classeCellule(c.key)} {...celluleProps(el.id, c.key)}>
                        <button type="button" className="cell-comment" onClick={() => setFicheId(el.id)}>
                          {texteReponse(c.champ, reponses[el.id]?.[c.champ.id], sousGroupes[c.champ.group_id]) || (
                            <span className="muted">—</span>
                          )}
                        </button>
                      </td>
                    ) : (
                      <Fragment key={c.key}>{cellules[c.key]}</Fragment>
                    ),
                  )}
                  <td>
                    <button
                      type="button"
                      className="icon-btn icon-btn--danger"
                      onClick={() => remove(el.id)}
                      aria-label={`Supprimer ${el.prenom}`}
                    >
                      <Icon name="trash" size={18} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        className="fab--secondary"
        onClick={() => setShowImport(true)}
        aria-label="Importer des élèves"
      >
        <Icon name="folder" size={20} />
      </button>
      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Ajouter un élève">
        <Icon name="plus" size={24} />
      </button>

      {eleveEnFiche && (
        <FicheEleve
          ecoleId={ecoleId}
          eleve={eleveEnFiche}
          cours={cours}
          onClose={() => setFicheId(null)}
          onEnregistre={(eleve) => {
            remplacer(eleve)
            relireColonnes() // les réponses aux champs de la fiche
          }}
          onFusionnee={() => {
            setFicheId(null)
            relireEleves()
          }}
        />
      )}

      {eleveAppuye && (
        <div className="cellule-popover-overlay" onClick={() => setPressed(null)}>
          <div className="cellule-popover-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{champAppuye?.label ?? CHAMP_LABEL[pressed.champ]}</h2>
              <button
                type="button"
                className="icon-btn"
                onClick={() => setPressed(null)}
                aria-label="Fermer"
              >
                <Icon name="x" />
              </button>
            </div>
            <p className="muted">
              {eleveAppuye.prenom} {eleveAppuye.nom}
            </p>
            <p className="cellule-popover__valeur">
              {valeurAppuyee() || <span className="muted">(vide)</span>}
            </p>
            <div className="cellule-popover__actions">
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => copierValeur(valeurAppuyee())}
              >
                <Icon name="fileCheck" size={16} /> {copieOk ? 'Copié !' : 'Copier dans le presse-papier'}
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  toggleCelluleRouge(eleveAppuye.id, pressed.champ)
                  setPressed(null)
                }}
              >
                {surlignageDe(eleveAppuye.id).cellulesRouges.includes(pressed.champ)
                  ? 'Retirer le rouge de cette cellule'
                  : 'Marquer cette cellule en rouge'}
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  toggleLigneRouge(eleveAppuye.id)
                  setPressed(null)
                }}
              >
                {surlignageDe(eleveAppuye.id).ligneRouge
                  ? 'Retirer le rouge de la ligne'
                  : 'Marquer toute la ligne en rouge'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showAdd && <AddEleveModal onClose={() => setShowAdd(false)} onAdd={addEleve} />}

      {showImport && (
        <IntegrerFichierElevesModal
          ecoleId={ecoleId}
          cours={cours}
          setEleves={setEleves}
          onClose={() => setShowImport(false)}
        />
      )}
    </div>
  )
}

function AddEleveModal({ onClose, onAdd }) {
  const [nom, setNom] = useState('')
  const [prenom, setPrenom] = useState('')
  // Garde-fou contre un double-clic/double-appel (l'appel est async
  // désormais, voir addEleve dans AdminEleves) : sans ça, un deuxième clic
  // pendant que le premier est encore en vol créerait 2 élèves.
  const [enCours, setEnCours] = useState(false)

  async function valider() {
    if (enCours) return
    setEnCours(true)
    await onAdd(nom, prenom)
    onClose()
  }

  return (
    <Modal
      title="Ajouter un élève"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!nom || !prenom || enCours}
          onClick={valider}
        >
          Ajouter
        </button>
      }
    >
      <label htmlFor="add-prenom">Prénom</label>
      <input id="add-prenom" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
      <label htmlFor="add-nom">Nom</label>
      <input id="add-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
    </Modal>
  )
}
