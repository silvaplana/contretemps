import { paiementLabels } from '../../data/paiement.js'
import { ROLE_LABEL } from '../../data/roles.js'
import { calculerAge } from '../../utils/age.js'
import Icon from '../../components/Icon.jsx'

// "Carte" de profil (voir ConversationListScreen.jsx : cliquer l'avatar
// d'une ligne l'ouvre) — inspirée d'une capture WhatsApp fournie par
// l'utilisateur (fiche d'un contact/groupe partagé) : avatar en grand,
// nom, et seulement 2 actions — "Message" (ouvre/crée la discussion) et
// "i" (bascule sur un 2e écran, plus détaillé).
//
// `vueInfos` est CONTRÔLÉ par MessagerieScreen (pas un état local ici) :
// depuis la fiche Infos d'un groupe, cliquer l'icône d'un membre empile
// directement SA fiche Infos par-dessus (voir onMembreClick) — un simple
// état local ne pourrait pas distinguer "retour vers ma carte" de "retour
// vers la liste des membres du groupe précédent", voir MessagerieScreen.jsx.
//
// `cible` :
//   { type: 'conversation', conversation }  — discussion déjà existante
//   { type: 'contact', compte }             — pas encore de discussion
export default function ProfilContactScreen({
  cible,
  vueInfos,
  compteId,
  viewerRole,
  eleves,
  cours,
  onBackCarte,
  onShowInfos,
  onHideInfos,
  onMembreClick,
  onMessage,
  contacterEnCours,
}) {
  const { nom, sousTitre, estGroupe, initiales, membres, personneId, role } = resoudreAffichage(cible, compteId)
  // Fiche complète élève (allergies, contacts parents, paiement...) —
  // décision utilisateur explicite : réservée à Admin/Professeur, jamais
  // à un autre Élève (voir AskUserQuestion — recherche globale par
  // ailleurs, mais ces champs restent sensibles pour des mineurs).
  const peutVoirDetails = viewerRole === 'admin' || viewerRole === 'professeur'
  const detailEleve =
    !estGroupe && role === 'eleve' && peutVoirDetails ? trouverDetailEleve(personneId, eleves, cours) : null

  // Couleur d'avatar Admin/Professeur distincte de celle d'un élève
  // (décision utilisateur explicite, voir .avatar--staff dans App.css et
  // ConversationListScreen.jsx : estStaff, même règle).
  const classeAvatar = estGroupe ? 'avatar--groupe' : role === 'admin' || role === 'professeur' ? 'avatar--staff' : ''
  const avatar = (
    <span className={`avatar avatar--lg ${classeAvatar}`}>
      {estGroupe ? <Icon name="users" size={40} /> : initiales}
    </span>
  )

  if (vueInfos) {
    return (
      <div className="thread-screen">
        <EnTete titre="Infos" onBack={onHideInfos} />
        <div className="profil-contact-screen__body">
          {avatar}
          <h2>{nom}</h2>
          {sousTitre && <p className="muted">{sousTitre}</p>}
          {membres && (
            <div className="profil-contact-screen__membres">
              <p className="conversation-list__section">
                {membres.length} membre{membres.length > 1 ? 's' : ''}
              </p>
              {membres.map((m) => (
                <div key={m.id} className="profil-contact-screen__membre">
                  {/* Voir doc de tête de fichier — cliquable seulement
                      pour Admin/Professeur (voir onMembreClick). */}
                  {peutVoirDetails ? (
                    <button
                      type="button"
                      className={`avatar avatar--sm conversation-list__avatar-btn ${m.role === 'admin' || m.role === 'professeur' ? 'avatar--staff' : ''}`}
                      onClick={() => onMembreClick(m)}
                      aria-label={`Profil de ${m.prenom} ${m.nom}`}
                    >
                      {`${m.prenom[0] ?? ''}${m.nom[0] ?? ''}`.toUpperCase()}
                    </button>
                  ) : (
                    <span
                      className={`avatar avatar--sm ${m.role === 'admin' || m.role === 'professeur' ? 'avatar--staff' : ''}`}
                    >
                      {`${m.prenom[0] ?? ''}${m.nom[0] ?? ''}`.toUpperCase()}
                    </span>
                  )}
                  <span className="profil-contact-screen__membre-nom">
                    {m.prenom} {m.nom}
                  </span>
                  <span className="muted">{ROLE_LABEL[m.role] ?? m.role}</span>
                </div>
              ))}
            </div>
          )}
          {detailEleve && <DetailsEleve detail={detailEleve} />}
        </div>
      </div>
    )
  }

  return (
    <div className="thread-screen">
      <EnTete titre={nom} onBack={onBackCarte} />
      <div className="profil-contact-screen__body">
        {avatar}
        <h2>{nom}</h2>
        {sousTitre && <p className="muted">{sousTitre}</p>}
        <div className="profil-contact-screen__actions">
          <button
            type="button"
            className="profil-contact-screen__action"
            onClick={onMessage}
            disabled={contacterEnCours}
          >
            <span className="icon-btn icon-btn--accent">
              <Icon name="messagerie" size={22} />
            </span>
            Message
          </button>
          <button type="button" className="profil-contact-screen__action" onClick={onShowInfos}>
            <span className="icon-btn icon-btn--accent">
              <Icon name="info" size={22} />
            </span>
            Infos
          </button>
        </div>
      </div>
    </div>
  )
}

function EnTete({ titre, onBack }) {
  return (
    <div className="thread-screen__header">
      <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour">
        <Icon name="chevronLeft" size={20} />
      </button>
      <strong>{titre}</strong>
    </div>
  )
}

// Fiche complète élève (voir plus haut, `detailEleve`) — mêmes champs que
// Admin > Élèves (AdminEleves.jsx), en lecture seule, un par ligne. Une
// ligne dont la valeur est vide ne s'affiche pas (DetailLigne) : moins
// bruyant qu'une valeur à valeur "—" partout sur une fiche déjà longue.
function DetailsEleve({ detail }) {
  return (
    <div className="profil-contact-screen__details">
      <DetailLigne label="Cours suivis" valeur={detail.coursNoms.join(', ')} />
      <DetailLigne
        label="Date de naissance"
        valeur={detail.dateNaissance && (detail.age != null ? `${detail.dateNaissance} (${detail.age} ans)` : detail.dateNaissance)}
      />
      <DetailLigne label="Téléphone" valeur={detail.telephone} />
      <DetailLigne label="Email" valeur={detail.email} />
      <DetailLigne label="Adresse" valeur={detail.adresse} />
      <DetailLigne label="Santé" valeur={detail.sante.join(' · ')} />
      <DetailLigne label="Certificat médical" valeur={detail.certificatMedical ? 'Reçu' : 'Manquant'} />
      <DetailLigne
        label="Paiement"
        valeur={`${paiementLabels[detail.statutPaiement] ?? detail.statutPaiement} — ${detail.montantPaye}€ / ${detail.montantTotalAnnee}€`}
      />
      <DetailLigne label="Commentaire admin" valeur={detail.commentaireAdmin} />
      {detail.contacts.length > 0 && (
        <>
          <p className="conversation-list__section">Contacts</p>
          {detail.contacts.map((c) => (
            <DetailLigne
              key={c.id}
              label={`${c.prenom} ${c.nom} (${c.lien})`}
              valeur={[c.telephone, c.email].filter(Boolean).join(' — ')}
            />
          ))}
        </>
      )}
    </div>
  )
}

function DetailLigne({ label, valeur }) {
  if (!valeur) return null
  return (
    <div className="profil-contact-screen__detail">
      <span className="muted">{label}</span>
      <span>{valeur}</span>
    </div>
  )
}

// Une conversation de groupe porte déjà tout (nom, membres résolus, voir
// api/messages.js) ; un contact brut (pas encore de discussion) n'a que
// nom/prénom/role — pas de liste de membres à afficher pour lui, il EST
// la personne. `personneId`/`role` (null pour un groupe) servent à
// résoudre la fiche complète élève ci-dessus.
function resoudreAffichage(cible, compteId) {
  if (cible.type === 'conversation') {
    const c = cible.conversation
    if (c.type === 'individuelle') {
      const autre = c.membres.find((m) => m.id !== compteId)
      return {
        nom: c.nom,
        sousTitre: autre ? ROLE_LABEL[autre.role] : undefined,
        estGroupe: false,
        initiales: c.nom.slice(0, 2).toUpperCase(),
        membres: null,
        personneId: autre?.id ?? null,
        role: autre?.role ?? null,
      }
    }
    return {
      nom: c.nom,
      sousTitre: undefined,
      estGroupe: true,
      initiales: null,
      membres: c.membres,
      personneId: null,
      role: null,
    }
  }
  const p = cible.compte
  return {
    nom: `${p.prenom} ${p.nom}`,
    sousTitre: ROLE_LABEL[p.role],
    estGroupe: false,
    initiales: `${p.prenom[0] ?? ''}${p.nom[0] ?? ''}`.toUpperCase(),
    membres: null,
    personneId: p.id,
    role: p.role,
  }
}

// `eleves`/`cours` viennent de App.jsx (déjà chargés pour Admin > Élèves)
// — un membre de conversation résolu côté backend (CompteResume) n'a que
// id/nom/prenom/role, jamais ces champs détaillés : on les retrouve ici
// par id plutôt que de les faire remonter par l'API messagerie.
function trouverDetailEleve(personneId, eleves, cours) {
  const el = eleves.find((e) => e.id === personneId)
  if (!el) return null
  return {
    coursNoms: el.coursIds.map((cid) => cours.find((c) => c.id === cid)?.nom).filter(Boolean),
    dateNaissance: el.dateNaissance,
    age: calculerAge(el.dateNaissance),
    telephone: el.telephone,
    email: el.email,
    adresse: el.adresse,
    sante: [
      el.allergies && `Allergies : ${el.allergies}`,
      el.traitementMedical && `Traitement : ${el.traitementMedical}`,
      el.informationsImportantes && `Infos : ${el.informationsImportantes}`,
    ].filter(Boolean),
    certificatMedical: el.certificatMedical,
    statutPaiement: el.statutPaiement,
    montantPaye: el.montantPaye,
    montantTotalAnnee: el.montantTotalAnnee,
    commentaireAdmin: el.commentaireAdmin,
    contacts: el.contactsEleve ?? [],
  }
}
