import { useEffect, useRef, useState } from 'react'
import * as administrateursApi from '../../api/administrateurs.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { isOwner } from '../../data/roles.js'
import { useFermerAuClicExterieur } from '../../hooks/useFermerAuClicExterieur.js'

// Tableau des administrateurs (Admin > École, au-dessus de "Usage vidéo" —
// voir spec/SPEC.md §2.4). Visible par TOUS les admins de l'école ; seuls
// les Owners ont le crayon et la poubelle, et jamais sur leur propre ligne.
// Créer un administrateur : menu ⋮ en haut à droite de CETTE section,
// sur la ligne du titre (demande du 2026-09-21 — ni un bouton sous le
// tableau, ni le menu ⋮ général de l'onglet, réservé aux sauvegardes).
//
// Les droits sont de toute façon vérifiés par le serveur (voir
// backend/src/administrateurs/receiver.py) : masquer les boutons ici n'est
// qu'un confort, pas la protection.
export default function AdministrateursTableau({ ecoleId, activeUser, professeurs, eleves = [] }) {
  const [administrateurs, setAdministrateurs] = useState([])
  const [creationOuverte, setCreationOuverte] = useState(false)
  const [menuOuvert, setMenuOuvert] = useState(false)
  const menuRef = useRef(null)
  useFermerAuClicExterieur(menuRef, menuOuvert, () => setMenuOuvert(false))
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
    const message = admin.estProf || admin.estEleve
      ? `Retirer les droits d’administrateur de ${admin.prenom} ${admin.nom} ? Son compte de ${admin.estProf ? 'professeur' : 'élève'} est conservé.`
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

  // Un professeur ou un élève déjà administrateur ne se promeut pas une 2e fois.
  const pasEncoreAdmin = (c) => !administrateurs.some((a) => a.id === c.id)
  const profsPromouvables = professeurs.filter(pasEncoreAdmin)
  const elevesPromouvables = eleves.filter(pasEncoreAdmin)

  return (
    <section className="admin-administrateurs">
      <div className="admin-section__entete">
        <h3 className="section-label">Administrateurs</h3>
        {peutGerer && (
          <div className="header-menu" ref={menuRef}>
            <button
              type="button"
              className="icon-btn"
              onClick={() => setMenuOuvert((o) => !o)}
              aria-label="Menu administrateurs"
            >
              <Icon name="moreVertical" />
            </button>
            {menuOuvert && (
              <div className="dropdown-menu header-menu__panel">
                <button
                  type="button"
                  onClick={() => {
                    setMenuOuvert(false)
                    setCreationOuverte(true)
                  }}
                >
                  <Icon name="users" size={18} /> Ajouter un administrateur
                </button>
              </div>
            )}
          </div>
        )}
      </div>
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
                  {a.estEleve && <Badge tone="neutral">Élève</Badge>}
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
          professeurs={profsPromouvables}
          eleves={elevesPromouvables}
          onValider={(donnees) => administrateursApi.creer(ecoleId, donnees)}
          onEnregistre={enregistree}
          onClose={() => setCreationOuverte(false)}
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
// - création : nouveau compte (nom, prénom, email) OU professeur ou élève
//   existant (un élève-admin n'a ses droits qu'avec le code Admin, §2.4) ;
//   code de récupération obligatoire dans les deux cas ;
// - modification : pour un professeur-admin, seulement le code de
//   récupération et le statut Owner (le reste vient d'Admin > Profs).
// Le code de récupération n'est jamais relu (le serveur ne le renvoie
// pas) : en modification, champ vide = inchangé.
function AdministrateurModal({ admin, professeurs = [], eleves = [], onValider, onEnregistre, onClose }) {
  const enCreation = !admin
  const [facon, setFacon] = useState('nouveau')
  const [compteId, setCompteId] = useState('')
  const [nom, setNom] = useState(admin?.nom ?? '')
  const [prenom, setPrenom] = useState(admin?.prenom ?? '')
  const [email, setEmail] = useState(admin?.email ?? '')
  const [codeRecuperation, setCodeRecuperation] = useState('')
  const [owner, setOwner] = useState(admin?.estOwner ?? false)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  const promotion = enCreation && facon !== 'nouveau'
  const candidats = facon === 'eleve' ? eleves : professeurs
  const identiteModifiable = enCreation ? !promotion : !admin.estProf && !admin.estEleve

  const valide = enCreation
    ? codeRecuperation.trim() && (promotion ? compteId : nom.trim() && prenom.trim())
    : !identiteModifiable || (nom.trim() && prenom.trim())

  async function valider() {
    if (!valide || enCours) return
    setEnCours(true)
    setErreur(null)
    let donnees
    if (enCreation) {
      donnees = promotion
        ? { compteId: Number(compteId), codeRecuperation: codeRecuperation.trim(), owner }
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
            {[
              ['professeur', 'Un professeur de l’école', professeurs],
              ['eleve', 'Un élève de l’école', eleves],
            ].map(([valeur, libelle, liste]) => (
              <label key={valeur} className="checkbox-inline">
                <input
                  type="radio"
                  name="admin-facon"
                  checked={facon === valeur}
                  onChange={() => {
                    setFacon(valeur)
                    setCompteId('')
                  }}
                  disabled={liste.length === 0}
                />
                {libelle}
                {liste.length === 0 && <span className="muted"> (aucun disponible)</span>}
              </label>
            ))}
          </>
        )}

        {promotion && (
          <>
            <label htmlFor="admin-compte">{facon === 'eleve' ? 'Élève' : 'Professeur'}</label>
            <select
              id="admin-compte"
              className="field-input"
              value={compteId}
              onChange={(e) => setCompteId(e.target.value)}
            >
              <option value="">Choisir…</option>
              {[...candidats]
                .sort((a, b) => `${a.nom} ${a.prenom}`.localeCompare(`${b.nom} ${b.prenom}`, 'fr'))
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.prenom} {c.nom}
                  </option>
                ))}
            </select>
            {facon === 'eleve' && (
              <p className="muted">
                Il n’aura ses droits d’administrateur qu’en se connectant avec le code d’accès Admin de l’école :
                avec le code Élève, il reste un simple élève.
              </p>
            )}
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
        {!enCreation && (admin.estProf || admin.estEleve) && (
          <p className="muted">
            Son nom, son prénom et son email se modifient depuis Admin &gt; {admin.estProf ? 'Profs' : 'Élèves'}.
          </p>
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
