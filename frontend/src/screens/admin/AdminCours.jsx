import { useEffect, useRef, useState } from 'react'
import * as comptesApi from '../../api/comptes.js'
import * as conversationsApi from '../../api/conversations.js'
import * as coursApi from '../../api/cours.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { useFermerAuClicExterieur } from '../../hooks/useFermerAuClicExterieur.js'
import { correspond } from '../../utils/recherche.js'
import ConversationEditModal from './ConversationEditModal.jsx'
import PlanningHebdoView from './PlanningHebdoView.jsx'
import { useConversationEditor } from './useConversationEditor.js'

const MAX_BADGES = 2

// Choix fermé plutôt qu'un texte libre : évite les variantes ("mer.",
// "Mercredi ", fautes de frappe...) qui compliqueraient un jour un
// regroupement/tri par jour.
const JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

// Onglet Admin > Cours (voir spec/SPEC.md §5.1.4 et images/admin-cours.png).
// "Élèves inscrits" est dérivé de eleves[].coursIds (relation portée côté
// élève, voir schéma section 6) : lecture seule ici, ça se modifie depuis
// l'onglet Élèves. Les autres champs se modifient via la modale (icône
// stylo) plutôt qu'en ligne : ça couvre aussi la Salle, absente du tableau.
// Le menu 3 points (en-tête) ouvre le planning hebdomadaire (§5.1.4).
//
// Données métier via api/cours.js (voir api/README.md, et sa note sur la
// simplification "un seul professeur par cours" côté maquette/écrans).
export default function AdminCours({ cours, setCours, professeurs, eleves, ecoleId, groupes, setGroupes }) {
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [editId, setEditId] = useState(null)
  const [menuOuvert, setMenuOuvert] = useState(false)
  const [vue, setVue] = useState('liste')
  // Id du cours en cours de glisser-déposer (réordonnancement, voir
  // onDrop) — null hors glissement.
  const [dragId, setDragId] = useState(null)
  const [admins, setAdmins] = useState([])
  const menuRef = useRef(null)
  useFermerAuClicExterieur(menuRef, menuOuvert, () => setMenuOuvert(false))

  // Demande utilisateur du 2026-09-18 (précisée le 2026-09-21 : case à
  // cocher plutôt qu'une confirmation, et surtout rester sur cet onglet
  // plutôt que de basculer sur Admin > Messagerie) : à la création d'un
  // cours, proposer de créer sa conversation de groupe tout de suite.
  // Même logique de modale que "+" dans AdminGroupes.jsx, partagée via
  // ConversationEditModal.jsx / useConversationEditor.js — préfixé
  // `conversation` pour ne pas entrer en collision avec `editId`/
  // `enEdition` ci-dessus, qui concernent l'édition d'un COURS.
  const {
    setEditId: setConversationEditId,
    enEdition: conversationEnEdition,
    nouvelle: conversationNouvelle,
    renameGroupe,
    addMembre,
    removeMembre,
    creerGroupeWhatsapp,
    fermerEdition: fermerEditionConversation,
  } = useConversationEditor(groupes, setGroupes)

  // Uniquement utile pour la modale de conversation ci-dessus (voir
  // AddMembreForm : "Ajouter un membre" > Admin), comme dans
  // AdminGroupes.jsx.
  useEffect(() => {
    comptesApi.listerAdmins(ecoleId).then(setAdmins)
  }, [ecoleId])

  const filtered = cours.filter((c) => correspond(c.nom, search))
  const enEdition = cours.find((c) => c.id === editId)

  if (vue === 'planning') {
    return (
      <PlanningHebdoView
        cours={cours}
        professeurs={professeurs}
        onBack={() => setVue('liste')}
      />
    )
  }

  function remplacer(coursMisAJour) {
    setCours((list) => list.map((c) => (c.id === coursMisAJour.id ? coursMisAJour : c)))
  }

  async function update(id, patch) {
    remplacer(await coursApi.modifier(id, patch))
  }

  async function remove(id) {
    if (!window.confirm('Supprimer ce cours ?')) return
    await coursApi.supprimer(id)
    setCours((list) => list.filter((c) => c.id !== id))
  }

  async function addCours({ avecConversation, ...donnees }) {
    const nouveau = await coursApi.creer(ecoleId, donnees)
    // Voir AdminEleves.jsx : updater idempotent, StrictMode (dev) peut
    // l'appliquer 2 fois de suite sur son propre résultat.
    setCours((list) => (list.some((c) => c.id === nouveau.id) ? list : [...list, nouveau]))

    if (!avecConversation) return
    // Même recette que le "+" d'Admin > Messagerie (voir
    // AdminGroupes.jsx: creerConversation), sa modale d'édition s'ouvre
    // juste après — SANS bloc "cours" (voir demande du 2026-09-21), le
    // nom du cours est repris tel quel comme nom de la conversation
    // (demande du 2026-09-21 : proposé, pas juste dérivé à l'affichage
    // via nomAffiche/estVide comme le ferait un bloc "cours" — modifiable
    // ensuite dans la modale avant de cliquer "Valider"). Le professeur
    // du cours (s'il y en a un — voir §6.5, "0 prof" est un cas normal),
    // lui, est pré-ajouté comme membre : `nouveau.professeurId` (renvoyé
    // par l'API, donc bien typé) plutôt que le `professeurId` du
    // formulaire (une chaîne, valeur brute d'un <select>).
    const conversation = await conversationsApi.creerGroupe(ecoleId, nouveau.nom)
    let membres = []
    if (nouveau.professeurId) {
      await conversationsApi.ajouterMembre(conversation.id, { type: 'professeur', id: nouveau.professeurId })
      membres = [{ type: 'professeur', id: nouveau.professeurId }]
    }
    setGroupes((list) => [...list, { ...conversation, membres }])
    setConversationEditId(conversation.id, { nouvelle: true })
  }

  function elevesDuCours(coursId) {
    return eleves.filter((el) => el.coursIds.includes(coursId))
  }

  // Réordonnancement par glisser-déposer (poignée dans la 1re colonne) —
  // désactivé pendant une recherche (voir `search`) : l'ordre visible
  // serait celui du sous-ensemble filtré, pas l'ordre réel complet.
  function onDropCours(cibleId) {
    if (dragId == null || dragId === cibleId) {
      setDragId(null)
      return
    }
    const from = cours.findIndex((c) => c.id === dragId)
    const to = cours.findIndex((c) => c.id === cibleId)
    setDragId(null)
    if (from === -1 || to === -1) return
    const reordonne = [...cours]
    const [deplace] = reordonne.splice(from, 1)
    reordonne.splice(to, 0, deplace)
    // Ancien `ordre` par id, pour ne persister que les cours dont la
    // position a réellement changé (pas tous à chaque glissement).
    const anciensOrdres = new Map(cours.map((c) => [c.id, c.ordre]))
    const avecNouvelOrdre = reordonne.map((c, i) => ({ ...c, ordre: i }))
    setCours(avecNouvelOrdre)
    avecNouvelOrdre
      .filter((c) => anciensOrdres.get(c.id) !== c.ordre)
      .forEach((c) => {
        coursApi.modifier(c.id, { ordre: c.ordre }).catch(() => {
          // Échec silencieux : au pire l'ordre visible et l'ordre en base
          // divergent jusqu'au prochain rechargement, pas bloquant pour
          // une simple réorganisation d'affichage.
        })
      })
  }

  return (
    <div className="admin-panel">
      <div className="admin-panel__toolbar">
        <div className="search-bar">
          <Icon name="search" size={18} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher un cours"
          />
        </div>
        <div className="header-menu" ref={menuRef}>
          <button
            type="button"
            className="icon-btn"
            onClick={() => setMenuOuvert((o) => !o)}
            aria-label="Menu"
          >
            <Icon name="moreVertical" />
          </button>
          {menuOuvert && (
            <div className="dropdown-menu header-menu__panel">
              <button
                type="button"
                onClick={() => {
                  setVue('planning')
                  setMenuOuvert(false)
                }}
              >
                <Icon name="presence" size={18} /> Planning hebdomadaire
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th aria-label="Réordonner" />
              <th>Cours</th>
              <th>Horaire</th>
              <th>Prof</th>
              <th>Élèves</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => {
              const inscrits = elevesDuCours(c.id)
              const prof = professeurs.find((p) => p.id === c.professeurId)
              return (
                <tr
                  key={c.id}
                  draggable={!search}
                  onDragStart={() => setDragId(c.id)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => onDropCours(c.id)}
                  onDragEnd={() => setDragId(null)}
                  className={dragId === c.id ? 'data-table__row--dragged' : undefined}
                >
                  <td>
                    {!search && (
                      <span className="drag-handle" title={`Glisser pour réordonner ${c.nom}`}>
                        <Icon name="grip" size={16} />
                      </span>
                    )}
                  </td>
                  <td className="data-table__name">{c.nom}</td>
                  <td>
                    {c.jour} {c.heureDebut}-{c.heureFin}
                    {c.horairesSupplementaires?.map((h, i) => (
                      <div key={i} className="muted">
                        {h.jour} {h.heureDebut}-{h.heureFin}
                      </div>
                    ))}
                  </td>
                  <td>{prof ? `${prof.prenom} ${prof.nom.charAt(0)}.` : <span className="muted">—</span>}</td>
                  <td>
                    <div className="badge-list">
                      {inscrits.slice(0, MAX_BADGES).map((el) => (
                        <Badge key={el.id}>{el.prenom}</Badge>
                      ))}
                      {inscrits.length > MAX_BADGES && (
                        <Badge tone="neutral">+{inscrits.length - MAX_BADGES}</Badge>
                      )}
                      {inscrits.length === 0 && <span className="muted">—</span>}
                    </div>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        type="button"
                        className="icon-btn"
                        onClick={() => setEditId(c.id)}
                        aria-label={`Modifier ${c.nom}`}
                      >
                        <Icon name="edit" size={18} />
                      </button>
                      <button
                        type="button"
                        className="icon-btn icon-btn--danger"
                        onClick={() => remove(c.id)}
                        aria-label={`Supprimer ${c.nom}`}
                      >
                        <Icon name="trash" size={18} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Ajouter un cours">
        <Icon name="plus" size={24} />
      </button>

      {showAdd && (
        <CoursModal
          title="Ajouter un cours"
          submitLabel="Ajouter"
          professeurs={professeurs}
          onClose={() => setShowAdd(false)}
          onSubmit={addCours}
        />
      )}

      {enEdition && (
        <CoursModal
          title={`Modifier — ${enEdition.nom}`}
          submitLabel="Enregistrer"
          initial={enEdition}
          professeurs={professeurs}
          onClose={() => setEditId(null)}
          onSubmit={(donnees) => update(enEdition.id, donnees)}
        />
      )}

      {conversationEnEdition && (
        <ConversationEditModal
          conversation={conversationEnEdition}
          nouvelle={conversationNouvelle}
          admins={admins}
          professeurs={professeurs}
          eleves={eleves}
          cours={cours}
          onClose={fermerEditionConversation}
          onRename={(nom) => renameGroupe(conversationEnEdition.id, nom)}
          onAddMembre={(membre) => addMembre(conversationEnEdition.id, membre)}
          onRemoveMembre={(membre, index) => removeMembre(conversationEnEdition.id, membre, index)}
          onCreerGroupeWhatsapp={() => creerGroupeWhatsapp(conversationEnEdition.id)}
        />
      )}
    </div>
  )
}

// Formulaire complet (Nom, Jour, Horaire, Salle, Professeur) réutilisé pour
// l'ajout et la modification — `initial` pré-remplit les champs en édition.
function CoursModal({ title, submitLabel, initial, professeurs, onClose, onSubmit }) {
  const [nom, setNom] = useState(initial?.nom ?? '')
  // Case à cocher, uniquement à la CRÉATION (voir `!initial` ci-dessous) —
  // demande utilisateur du 2026-09-21 : cochée par défaut, à la place de
  // l'ancien `window.confirm` après coup (voir addCours dans
  // AdminCours.jsx).
  const [avecConversation, setAvecConversation] = useState(true)
  const [jour, setJour] = useState(initial?.jour ?? 'Mercredi')
  const [heureDebut, setHeureDebut] = useState(initial?.heureDebut ?? '')
  const [heureFin, setHeureFin] = useState(initial?.heureFin ?? '')
  // Créneaux EN PLUS du créneau ci-dessus — rare (voir api/cours.js et
  // backend/src/cours/models.py:Cours.horaires_supplementaires), ex. un
  // cours d'Éveil proposé aussi un autre jour.
  const [horairesSupplementaires, setHorairesSupplementaires] = useState(
    initial?.horairesSupplementaires ?? []
  )
  const [salle, setSalle] = useState(initial?.salle ?? '')
  // Pas de professeur choisi par défaut pour un nouveau cours (voir
  // §6.5 : "0 prof" est un cas normal, pas une erreur à combler) — un
  // cours en édition garde le sien.
  const [professeurId, setProfesseurId] = useState(initial?.professeurId ?? '')
  // Garde-fou contre un double-appel (voir AdminEleves.jsx) : l'appel est
  // async désormais.
  const [enCours, setEnCours] = useState(false)

  function ajouterHoraire() {
    setHorairesSupplementaires((h) => [...h, { jour: 'Mercredi', heureDebut: '', heureFin: '' }])
  }

  function retirerHoraire(index) {
    setHorairesSupplementaires((h) => h.filter((_, i) => i !== index))
  }

  function modifierHoraire(index, champ, valeur) {
    setHorairesSupplementaires((h) => h.map((horaire, i) => (i === index ? { ...horaire, [champ]: valeur } : horaire)))
  }

  async function valider() {
    if (enCours) return
    setEnCours(true)
    await onSubmit({
      nom,
      jour,
      heureDebut,
      heureFin,
      salle,
      professeurId,
      horairesSupplementaires,
      avecConversation: initial ? undefined : avecConversation,
    })
    onClose()
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!nom || enCours}
          onClick={valider}
        >
          {submitLabel}
        </button>
      }
    >
      <label htmlFor="cours-nom">Nom du cours</label>
      <input id="cours-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
      <label htmlFor="cours-jour">
        Jour{' '}
        <button
          type="button"
          className="icon-btn"
          onClick={ajouterHoraire}
          aria-label="Ajouter un autre jour pour ce cours"
          title="Ajouter un autre jour pour ce cours"
        >
          <Icon name="plus" size={14} />
        </button>
      </label>
      <select id="cours-jour" value={jour} onChange={(e) => setJour(e.target.value)}>
        {JOURS.map((j) => (
          <option key={j} value={j}>
            {j}
          </option>
        ))}
      </select>
      <label htmlFor="cours-debut">Heure de début</label>
      <input
        id="cours-debut"
        value={heureDebut}
        placeholder="17h00"
        onChange={(e) => setHeureDebut(e.target.value)}
      />
      <label htmlFor="cours-fin">Heure de fin</label>
      <input
        id="cours-fin"
        value={heureFin}
        placeholder="18h30"
        onChange={(e) => setHeureFin(e.target.value)}
      />

      {/* Créneaux en plus — rare (voir §6.5), ex. un cours proposé
          aussi un autre jour. */}
      {horairesSupplementaires.map((horaire, index) => (
        <div key={index} className="grille-2" style={{ alignItems: 'end', marginBottom: 8 }}>
          <div>
            <label htmlFor={`cours-jour-sup-${index}`}>Autre jour</label>
            <select
              id={`cours-jour-sup-${index}`}
              value={horaire.jour}
              onChange={(e) => modifierHoraire(index, 'jour', e.target.value)}
            >
              {JOURS.map((j) => (
                <option key={j} value={j}>
                  {j}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'end' }}>
            <div>
              <label htmlFor={`cours-debut-sup-${index}`}>Début</label>
              <input
                id={`cours-debut-sup-${index}`}
                value={horaire.heureDebut}
                placeholder="17h00"
                onChange={(e) => modifierHoraire(index, 'heureDebut', e.target.value)}
              />
            </div>
            <div>
              <label htmlFor={`cours-fin-sup-${index}`}>Fin</label>
              <input
                id={`cours-fin-sup-${index}`}
                value={horaire.heureFin}
                placeholder="18h30"
                onChange={(e) => modifierHoraire(index, 'heureFin', e.target.value)}
              />
            </div>
            <button
              type="button"
              className="icon-btn icon-btn--danger"
              onClick={() => retirerHoraire(index)}
              aria-label="Retirer ce créneau"
              title="Retirer ce créneau"
            >
              <Icon name="minus" size={14} />
            </button>
          </div>
        </div>
      ))}

      <label htmlFor="cours-salle">Salle</label>
      <input id="cours-salle" value={salle} onChange={(e) => setSalle(e.target.value)} />
      <label htmlFor="cours-prof">Professeur</label>
      {/* Un cours peut ne pas encore avoir de professeur déclaré (voir
          §6.5) — d'où cette option vide, pas de sélection forcée. */}
      <select id="cours-prof" value={professeurId} onChange={(e) => setProfesseurId(e.target.value)}>
        <option value="">— Aucun —</option>
        {professeurs.map((p) => (
          <option key={p.id} value={p.id}>
            {p.prenom} {p.nom}
          </option>
        ))}
      </select>

      {/* Uniquement à la création (voir avecConversation ci-dessus) —
          modifier un cours existant ne touche pas à sa conversation. */}
      {!initial && (
        <label className="checkbox-inline">
          <input
            type="checkbox"
            checked={avecConversation}
            onChange={(e) => setAvecConversation(e.target.checked)}
          />
          Créer aussi la conversation de groupe de ce cours
        </label>
      )}
    </Modal>
  )
}
