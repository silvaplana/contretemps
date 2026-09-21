import { useEffect, useState } from 'react'
import * as administrateursApi from '../../api/administrateurs.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { isOwner } from '../../data/roles.js'

// Tableau des administrateurs (Admin > École, au-dessus de "Usage vidéo" —
// voir spec/SPEC.md §2.4). Visible par TOUS les admins de l'école ; seuls
// les Owners ont le crayon et la poubelle, et jamais sur leur propre ligne.
// "Créer nouvel administrateur" est dans le menu ⋮ d'Admin > École (voir
// SauvegardeEcoleMenu.jsx) : `creationOuverte` vient de là.
//
// Les droits sont de toute façon vérifiés par le serveur (voir
// backend/src/administrateurs/receiver.py) : masquer les boutons ici n'est
// qu'un confort, pas la protection.
export default function AdministrateursTableau({ ecoleId, activeUser, professeurs, creationOuverte, onFermerCreation }) {
  const [administrateurs, setAdministrateurs] = useState([])
  const [enEdition, setEnEdition] = useState(null)
  const [erreur, setErreur] = useState(null)
  const peutGerer = isOwner(activeUser)

  useEffect(() => {
    let annule = false
    administrateursApi
      .lister(ecoleId)
      .then((liste) => {
        if (!annule) setAdministrateurs(liste)
      })
      .catch((err) => setErreur(err.message))
    return () => {
      annule = true
    }
  }, [ecoleId])

  async function supprimer(admin) {
    const message = admin.estProf
      ? `Retirer les droits d’administrateur de ${admin.prenom} ${admin.nom} ? Son compte de professeur est conservé.`
      : `Supprimer définitivement l’administrateur ${admin.prenom} ${admin.nom} ? Ses messages restent visibles dans les conversations.`
    if (!window.confirm(message)) return
    setErreur(null)
    try {
      await administrateursApi.supprimer(admin.id)
      setAdministrateurs((liste) => liste.filter((a) => a.id !== admin.id))
    } catch (err) {
      setErreur(err.message)
    }
  }

  // Création OU modification : la ligne est remplacée ou ajoutée telle que
  // renvoyée par le serveur (source de vérité, ex. statut Owner).
  function enregistree(admin) {
    setAdministrateurs((liste) =>
      liste.some((a) => a.id === admin.id) ? liste.map((a) => (a.id === admin.id ? admin : a)) : [...liste, admin],
    )
  }

  // Un professeur déjà administrateur ne se promeut pas une 2e fois.
  const promouvables = professeurs.filter((p) => !administrateurs.some((a) => a.id === p.id))

  return (
    <section className="admin-administrateurs">
      <h3 className="section-label">Administrateurs</h3>
      {erreur && <p className="admin-panel__erreur">{erreur}</p>}
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Prénom</th>
              <th>Email</th>
              <th>Administrateur principal</th>
              {peutGerer && <th aria-label="Actions" />}
            </tr>
          </thead>
          <tbody>
            {administrateurs.map((a) => (
              <tr key={a.id}>
                <td className="data-table__name">
                  {a.nom} {a.estProf && <Badge tone="neutral">Prof</Badge>}
                </td>
                <td>{a.prenom}</td>
                <td>{a.email || <span className="muted">—</span>}</td>
                <td>{a.estOwner ? <Badge>Oui</Badge> : <span className="muted">—</span>}</td>
                {peutGerer && (
                  <td>
                    {a.id !== activeUser.id && (
                      <div className="row-actions">
                        <button
                          type="button"
                          className="icon-btn"
                          onClick={() => setEnEdition(a)}
                          aria-label={`Modifier ${a.prenom} ${a.nom}`}
                        >
                          <Icon name="edit" size={18} />
                        </button>
                        <button
                          type="button"
                          className="icon-btn icon-btn--danger"
                          onClick={() => supprimer(a)}
                          aria-label={`Supprimer ${a.prenom} ${a.nom}`}
                        >
                          <Icon name="trash" size={18} />
                        </button>
                      </div>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {peutGerer && creationOuverte && (
        <AdministrateurModal
          professeurs={promouvables}
          onValider={(donnees) => administrateursApi.creer(ecoleId, donnees)}
          onEnregistre={enregistree}
          onClose={onFermerCreation}
        />
      )}
      {peutGerer && enEdition && (
        <AdministrateurModal
          admin={enEdition}
          onValider={(donnees) => administrateursApi.modifier(enEdition.id, donnees)}
          onEnregistre={enregistree}
          onClose={() => setEnEdition(null)}
        />
      )}
    </section>
  )
}

// Création (sans `admin`) ou modification (avec `admin`) — voir §2.4 :
// - création : nouveau compte (nom, prénom, email) OU professeur existant ;
//   code de récupération obligatoire dans les deux cas ;
// - modification : pour un professeur-admin, seulement le code de
//   récupération et le statut Owner (le reste vient d'Admin > Profs).
// Le code de récupération n'est jamais relu (le serveur ne le renvoie
// pas) : en modification, champ vide = inchangé.
function AdministrateurModal({ admin, professeurs = [], onValider, onEnregistre, onClose }) {
  const enCreation = !admin
  const [facon, setFacon] = useState('nouveau')
  const [professeurId, setProfesseurId] = useState('')
  const [nom, setNom] = useState(admin?.nom ?? '')
  const [prenom, setPrenom] = useState(admin?.prenom ?? '')
  const [email, setEmail] = useState(admin?.email ?? '')
  const [codeRecuperation, setCodeRecuperation] = useState('')
  const [owner, setOwner] = useState(admin?.estOwner ?? false)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  const promotion = enCreation && facon === 'professeur'
  const identiteModifiable = enCreation ? !promotion : !admin.estProf

  const valide = enCreation
    ? codeRecuperation.trim() && (promotion ? professeurId : nom.trim() && prenom.trim())
    : !identiteModifiable || (nom.trim() && prenom.trim())

  async function valider() {
    if (!valide || enCours) return
    setEnCours(true)
    setErreur(null)
    let donnees
    if (enCreation) {
      donnees = promotion
        ? { professeurId: Number(professeurId), codeRecuperation: codeRecuperation.trim(), owner }
        : { nom: nom.trim(), prenom: prenom.trim(), email: email.trim(), codeRecuperation: codeRecuperation.trim(), owner }
    } else {
      donnees = {
        ...(identiteModifiable && { nom: nom.trim(), prenom: prenom.trim(), email: email.trim() }),
        ...(codeRecuperation.trim() && { codeRecuperation: codeRecuperation.trim() }),
        ...(owner !== admin.estOwner && { owner }),
      }
    }
    try {
      onEnregistre(await onValider(donnees))
      onClose()
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Modal
      title={enCreation ? 'Créer un administrateur' : `Modifier ${admin.prenom} ${admin.nom}`}
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary btn--block" disabled={!valide || enCours} onClick={valider}>
          {enCreation ? 'Créer' : 'Enregistrer'}
        </button>
      }
    >
      <div className="form-fields">
        {enCreation && (
          <>
            <label className="checkbox-inline">
              <input type="radio" name="admin-facon" checked={facon === 'nouveau'} onChange={() => setFacon('nouveau')} />
              Nouveau compte
            </label>
            <label className="checkbox-inline">
              <input
                type="radio"
                name="admin-facon"
                checked={facon === 'professeur'}
                onChange={() => setFacon('professeur')}
                disabled={professeurs.length === 0}
              />
              Un professeur de l’école
              {professeurs.length === 0 && <span className="muted"> (aucun disponible)</span>}
            </label>
          </>
        )}

        {promotion && (
          <>
            <label htmlFor="admin-professeur">Professeur</label>
            <select
              id="admin-professeur"
              className="field-input"
              value={professeurId}
              onChange={(e) => setProfesseurId(e.target.value)}
            >
              <option value="">Choisir…</option>
              {professeurs.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.prenom} {p.nom}
                </option>
              ))}
            </select>
          </>
        )}

        {identiteModifiable && (
          <>
            <label htmlFor="admin-nom">Nom</label>
            <input id="admin-nom" className="field-input" value={nom} onChange={(e) => setNom(e.target.value)} />
            <label htmlFor="admin-prenom">Prénom</label>
            <input id="admin-prenom" className="field-input" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
            <label htmlFor="admin-email">Email</label>
            <input
              id="admin-email"
              className="field-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </>
        )}
        {!enCreation && admin.estProf && (
          <p className="muted">Son nom, son prénom et son email se modifient depuis Admin &gt; Profs.</p>
        )}

        <label htmlFor="admin-code">Code de récupération</label>
        <input
          id="admin-code"
          className="field-input"
          value={codeRecuperation}
          onChange={(e) => setCodeRecuperation(e.target.value)}
          placeholder={
            enCreation
              ? 'Nom de son 1er animal de compagnie'
              : admin.codeRecuperationDefini
                ? 'Défini — laisser vide pour ne pas le changer'
                : 'Non défini'
          }
        />

        <label className="checkbox-inline">
          <input type="checkbox" checked={owner} onChange={(e) => setOwner(e.target.checked)} />
          Administrateur principal (peut gérer les administrateurs)
        </label>

        {erreur && <p className="admin-panel__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}
