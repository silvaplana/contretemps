import { useEffect, useRef, useState } from 'react'
import * as administrateursApi from '../../api/administrateurs.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import ListeEmails from '../../components/ListeEmails.jsx'
import Modal from '../../components/Modal.jsx'
import { isOwner, isSuperuser } from '../../data/roles.js'
import { BoutonInviter, MessageAcces, StatutAcces, useAcces } from './AccesInvitation.jsx'

// Fonctions au bureau de l'association (spec/core.md §5.1), dans l'ordre du
// serveur (backend/src/groups/board.py) : des titres, aucun droit.
const BUREAU = [
  ['president', 'Président·e'],
  ['vice_president', 'Vice-président·e'],
  ['secretary', 'Secrétaire'],
  ['treasurer', 'Trésorier·e'],
]
const FINANCIER = '🔒 Accès au Financier'
const ANNULER_MS = 10000

// Les groupes d'un admin, en pastilles toutes du même gris (maquette
// « Admins nouveau style ») : « Bureau » avant ses fonctions, puis Profs, les
// groupes faits à la main, et les 🔒 droits.
function pastilles(admin, groupesEcole) {
  const fonctions = BUREAU.filter(([cle]) => admin.bureauFunctions.includes(cle)).map(([, libelle]) => libelle)
  return [
    ...(fonctions.length ? ['Bureau', ...fonctions] : []),
    ...(admin.estProf ? ['Profs'] : []),
    ...groupesEcole.filter((g) => admin.groups.includes(g.id)).map((g) => g.name),
    ...(admin.estTresorier ? [FINANCIER] : []),
  ]
}

// Tableau des administrateurs (Admin > École, au-dessus de "Usage vidéo" —
// voir spec/SPEC.md §2.4). Visible par TOUS les admins de l'école ; seuls
// les Owners ont le crayon et la poubelle, et jamais sur leur propre ligne.
// Créer un administrateur : entrée "Ajouter un administrateur" du menu ⋮
// de l'en-tête, à droite du badge (demande du 2026-09-21, voir
// AdminParametres.jsx) — ce tableau n'en porte que la modale.
//
// Les droits sont de toute façon vérifiés par le serveur (voir
// backend/src/administrateurs/receiver.py) : masquer les boutons ici n'est
// qu'un confort, pas la protection.
export default function AdministrateursTableau({
  ecoleId,
  activeUser,
  professeurs,
  eleves = [],
  creationOuverte,
  onFermerCreation,
  onMonRoleTresorier,
}) {
  const [ouvert, setOuvert] = useState(false)
  const [administrateurs, setAdministrateurs] = useState([])
  // Accès à l'appli (spec §2.2) : même bouton « Inviter » et même statut
  // que dans Admin > Élèves.
  const acces = useAcces(ecoleId)
  const emails = administrateurs.map((a) => `${a.id}:${a.email ?? ''}`).join('|')
  useEffect(() => {
    acces.recharger()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [emails])
  const [enEdition, setEnEdition] = useState(null)
  const [groupesDe, setGroupesDe] = useState(null)
  const [groupesEcole, setGroupesEcole] = useState([])
  const [toast, setToast] = useState(null)
  const minuteurToast = useRef(null)
  const [erreur, setErreur] = useState(null)
  const peutGerer = isOwner(activeUser)
  // 🔒 Groupes qui donnent un droit : administrateur principal et Super User.
  const peutDonnerDesDroits = peutGerer || isSuperuser(activeUser)

  useEffect(() => {
    let annule = false
    administrateursApi
      .lister(ecoleId)
      .then((liste) => {
        if (!annule) setAdministrateurs(liste)
      })
      .catch((err) => setErreur(err.message))
    administrateursApi
      .listerGroupes(ecoleId)
      .then((liste) => {
        if (!annule) setGroupesEcole(liste)
      })
      .catch((err) => setErreur(err.message))
    return () => {
      annule = true
    }
  }, [ecoleId])

  useEffect(() => () => clearTimeout(minuteurToast.current), [])

  function montrerToast(texte, annuler) {
    clearTimeout(minuteurToast.current)
    setToast({ texte, annuler })
    minuteurToast.current = setTimeout(() => setToast(null), ANNULER_MS)
  }

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

  // Un groupe coché ou décoché dans la feuille : enregistré tout de suite,
  // Annuler pendant 10 s (pas de confirmation).
  async function changerGroupe(admin, patch, nom, ajoute) {
    setErreur(null)
    const avant = {
      tresorier: { tresorier: admin.estTresorier },
      bureauFunctions: { bureauFunctions: admin.bureauFunctions },
      prof: { prof: admin.estProf },
      groups: { groups: admin.groups },
    }[Object.keys(patch)[0]]
    async function appliquer(changement) {
      const nouveau = await administrateursApi.modifier(admin.id, changement)
      enregistree(nouveau)
      setGroupesDe((ouvert) => (ouvert?.id === nouveau.id ? nouveau : ouvert))
      // Sa propre ligne : l'onglet Financier apparaît (ou part) tout de suite.
      if ('tresorier' in changement && admin.id === activeUser.id) onMonRoleTresorier?.(changement.tresorier)
    }
    try {
      await appliquer(patch)
      montrerToast(`${admin.prenom} ${admin.nom} ${ajoute ? 'ajouté·e à' : 'retiré·e de'} « ${nom} »`, () =>
        appliquer(avant),
      )
    } catch (err) {
      setErreur(err.message)
    }
  }

  async function nouveauGroupe(admin) {
    const nom = window.prompt('Nom du groupe')
    if (!nom?.trim()) return
    setErreur(null)
    try {
      const groupe = await administrateursApi.creerGroupe(ecoleId, nom.trim())
      setGroupesEcole((liste) => [...liste, groupe].sort((a, b) => a.name.localeCompare(b.name, 'fr')))
      await changerGroupe(admin, { groups: [...admin.groups, groupe.id] }, groupe.name, true)
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
      {/* Dépliable, fermée par défaut (demande du 2026-10-15). */}
      <h3 className="section-label">
        <button
          type="button"
          className="section-label__depliant"
          aria-expanded={ouvert}
          onClick={() => setOuvert((o) => !o)}
        >
          <Icon name={ouvert ? 'chevronDown' : 'chevronRight'} size={14} />
          Administrateurs
        </button>
      </h3>
      {ouvert && (
        <>
          {erreur && <p className="admin-panel__erreur">{erreur}</p>}
          <MessageAcces acces={acces} />
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nom</th>
                  <th>Prénom</th>
                  <th>Email</th>
                  <th>Administrateur principal</th>
                  {/* Remplace les colonnes « Accès au Financier » et
                      « Bureau » (spec/core.md §5.2). */}
                  <th>Groupes</th>
                  <th>Inviter</th>
                  <th>Statut</th>
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
                    {/* Tout admin change les groupes, sa ligne comprise ;
                        les 🔒 droits restent à l'administrateur principal. */}
                    <td className="admin-groupes__colonne">
                      <button
                        type="button"
                        className="admin-groupes__case"
                        onClick={() => setGroupesDe(a)}
                        aria-label={`Groupes de ${a.prenom} ${a.nom}`}
                      >
                        {pastilles(a, groupesEcole).map((nom) => (
                          <span key={nom} className="admin-groupes__pastille">
                            {nom}
                          </span>
                        ))}
                        {pastilles(a, groupesEcole).length === 0 && (
                          <span className="admin-groupes__choisir">Choisir…</span>
                        )}
                      </button>
                    </td>
                    <td>
                      <BoutonInviter acces={acces} compteId={a.id} prenom={a.prenom} />
                    </td>
                    <td>
                      <StatutAcces acces={acces} compteId={a.id} />
                    </td>
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
          {groupesDe && (
            <GroupesModal
              admin={groupesDe}
              groupesEcole={groupesEcole}
              peutDonnerDesDroits={peutDonnerDesDroits}
              onChanger={(patch, nom, ajoute) => changerGroupe(groupesDe, patch, nom, ajoute)}
              onNouveau={() => nouveauGroupe(groupesDe)}
              erreur={erreur}
              onClose={() => setGroupesDe(null)}
            />
          )}
          {toast && (
            <div className="admin-groupes__toast" role="status">
              <span>{toast.texte}</span>
              {toast.annuler && (
                <button
                  type="button"
                  onClick={async () => {
                    const annuler = toast.annuler
                    setToast(null)
                    try {
                      await annuler()
                    } catch (err) {
                      setErreur(err.message)
                    }
                  }}
                >
                  Annuler
                </button>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}

// Création (sans `admin`) ou modification (avec `admin`) — voir §2.4 :
// - création : nouveau compte (nom, prénom, email) OU professeur ou élève
//   existant. Son accès à l'appli se donne ensuite par le bouton
//   « Inviter » du tableau (spec §2.2) ;
// - modification : pour un professeur-admin ou un élève-admin, seulement
//   le statut d'administrateur principal (le reste vient d'Admin > Profs
//   ou d'Admin > Élèves).
function AdministrateurModal({ admin, professeurs = [], eleves = [], onValider, onEnregistre, onClose }) {
  const enCreation = !admin
  const [facon, setFacon] = useState('nouveau')
  const [compteId, setCompteId] = useState('')
  const [nom, setNom] = useState(admin?.nom ?? '')
  const [prenom, setPrenom] = useState(admin?.prenom ?? '')
  const [email, setEmail] = useState(admin?.email ?? '')
  const [owner, setOwner] = useState(admin?.estOwner ?? false)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  const promotion = enCreation && facon !== 'nouveau'
  const candidats = facon === 'eleve' ? eleves : professeurs
  const identiteModifiable = enCreation ? !promotion : !admin.estProf && !admin.estEleve

  const valide = enCreation
    ? promotion
      ? compteId
      : nom.trim() && prenom.trim()
    : !identiteModifiable || (nom.trim() && prenom.trim())

  async function valider() {
    if (!valide || enCours) return
    setEnCours(true)
    setErreur(null)
    let donnees
    if (enCreation) {
      donnees = promotion
        ? { compteId: Number(compteId), owner }
        : { nom: nom.trim(), prenom: prenom.trim(), email: email.trim(), owner }
    } else {
      donnees = {
        ...(identiteModifiable && { nom: nom.trim(), prenom: prenom.trim(), email: email.trim() }),
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
          </>
        )}

        {identiteModifiable && (
          <>
            <label htmlFor="admin-nom">Nom</label>
            <input id="admin-nom" className="field-input" value={nom} onChange={(e) => setNom(e.target.value)} />
            <label htmlFor="admin-prenom">Prénom</label>
            <input id="admin-prenom" className="field-input" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
            <label htmlFor="admin-email">Emails</label>
            <ListeEmails id="admin-email" valeur={email} onChange={setEmail} />
          </>
        )}
        {!enCreation && (admin.estProf || admin.estEleve) && (
          <p className="muted">
            Son nom, son prénom et son email se modifient depuis Admin &gt; {admin.estProf ? 'Profs' : 'Élèves'}.
          </p>
        )}

        <label className="checkbox-inline">
          <input type="checkbox" checked={owner} onChange={(e) => setOwner(e.target.checked)} />
          Administrateur principal (peut gérer les administrateurs)
        </label>

        {erreur && <p className="admin-panel__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}

// Groupes d'un administrateur (maquette « Admins nouveau style ») : chaque
// case s'enregistre tout de suite. Bureau et ses fonctions, Profs, les
// groupes faits à la main, « + Nouveau groupe… », puis les 🔒 droits (grisés
// sauf pour l'administrateur principal et le Super User).
function GroupesModal({ admin, groupesEcole, peutDonnerDesDroits, onChanger, onNouveau, erreur, onClose }) {
  function basculerFonction(cle, coche) {
    const fonctions = coche ? [...admin.bureauFunctions, cle] : admin.bureauFunctions.filter((f) => f !== cle)
    onChanger({ bureauFunctions: BUREAU.map(([c]) => c).filter((c) => fonctions.includes(c)) }, BUREAU.find(([c]) => c === cle)[1], coche)
  }

  function basculerGroupe(groupe, coche) {
    const ids = coche ? [...admin.groups, groupe.id] : admin.groups.filter((id) => id !== groupe.id)
    onChanger({ groups: ids }, groupe.name, coche)
  }

  return (
    <Modal
      title={`Groupes de ${admin.prenom} ${admin.nom}`}
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary btn--block" onClick={onClose}>
          OK
        </button>
      }
    >
      <div className="admin-groupes__feuille">
        <div className="admin-groupes__ligne admin-groupes__ligne--titre">Bureau</div>
        {BUREAU.map(([cle, libelle]) => (
          <label key={cle} className="admin-groupes__ligne admin-groupes__ligne--sous">
            <input
              type="checkbox"
              checked={admin.bureauFunctions.includes(cle)}
              onChange={(e) => basculerFonction(cle, e.target.checked)}
            />
            <span>{libelle}</span>
          </label>
        ))}
        <label className="admin-groupes__ligne">
          <input type="checkbox" checked={admin.estProf} onChange={(e) => onChanger({ prof: e.target.checked }, 'Profs', e.target.checked)} />
          <span>Profs</span>
        </label>
        {groupesEcole.map((g) => (
          <label key={g.id} className="admin-groupes__ligne">
            <input type="checkbox" checked={admin.groups.includes(g.id)} onChange={(e) => basculerGroupe(g, e.target.checked)} />
            <span>{g.name}</span>
          </label>
        ))}
        <label className={`admin-groupes__ligne${peutDonnerDesDroits ? '' : ' admin-groupes__ligne--grise'}`}>
          <input
            type="checkbox"
            checked={admin.estTresorier}
            disabled={!peutDonnerDesDroits}
            onChange={(e) => onChanger({ tresorier: e.target.checked }, FINANCIER, e.target.checked)}
          />
          <span>{FINANCIER}</span>
        </label>
        {!peutDonnerDesDroits && (
          <p className="muted">🔒 : seuls l’administrateur principal et le Super User changent ces groupes.</p>
        )}
        <button type="button" className="btn btn--ghost admin-groupes__nouveau" onClick={onNouveau}>
          + Nouveau groupe…
        </button>
        {erreur && <p className="admin-panel__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}
