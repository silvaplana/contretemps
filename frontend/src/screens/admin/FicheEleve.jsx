import { useEffect, useState } from 'react'
import * as champsApi from '../../api/champs.js'
import * as elevesApi from '../../api/eleves.js'
import Icon from '../../components/Icon.jsx'
import ListeEmails from '../../components/ListeEmails.jsx'
import Modal from '../../components/Modal.jsx'
import { paiementLabels } from '../../data/paiement.js'
import { calculerAge } from '../../utils/age.js'
import { texteReponse } from '../../utils/reponses.js'
import FusionnerAvec from './FusionnerAvec.jsx'

// Fiche d'un élève (Admin > Élèves, demande du 2026-10-15) : ouverte d'un
// clic sur une ligne du tableau, qui n'est plus modifiable. Elle s'ouvre en
// lecture ; « Modifier » rend les champs modifiables, « Valider » enregistre
// tout d'un coup, « Annuler » revient à la fiche sans rien changer.
// Le prénom et le nom sont deux champs séparés : l'ancienne case unique
// « Prénom Nom » du tableau coupait un prénom composé (« Anne Sophie »).

const CHAMPS_TEXTE = [
  'prenom',
  'nom',
  'dateNaissance',
  'telephone',
  'email',
  'adresse',
  'statutPaiement',
  'montantTotalAnnee',
  'montantPaye',
  'commentaireAdmin',
  'allergies',
  'traitementMedical',
  'informationsImportantes',
]

function brouillonDe(eleve, reponses) {
  const brouillon = {
    coursIds: [...eleve.coursIds],
    contacts: eleve.contactsEleve.map((c) => ({ ...c })),
    champs: Object.fromEntries(reponses.map((r) => [r.field.id, r.value])),
  }
  for (const cle of CHAMPS_TEXTE) brouillon[cle] = eleve[cle] ?? ''
  return brouillon
}

function dateFrancaise(iso) {
  if (!iso) return ''
  const [a, m, j] = iso.split('-')
  return `${j}/${m}/${a}`
}

export default function FicheEleve({ ecoleId, eleve, cours, onClose, onEnregistre, onFusionnee }) {
  const [fusionOuverte, setFusionOuverte] = useState(false)
  const [brouillon, setBrouillon] = useState(null) // null = lecture
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const enEdition = brouillon !== null
  // Les champs de l'école (spec/core.md §4.3) et leurs réponses.
  const [reponses, setReponses] = useState([])
  const [sousGroupes, setSousGroupes] = useState({})

  useEffect(() => {
    champsApi.reponses(eleve.id).then(setReponses).catch(() => setReponses([]))
    champsApi
      .groupes(ecoleId)
      .then((choix) => setSousGroupes(Object.fromEntries(choix.parents.map((g) => [g.id, g.children]))))
      .catch(() => setSousGroupes({}))
  }, [ecoleId, eleve.id])

  function changerChamp(id, valeur) {
    setBrouillon((b) => ({ ...b, champs: { ...b.champs, [id]: valeur } }))
  }

  function changer(cle, valeur) {
    setBrouillon((b) => ({ ...b, [cle]: valeur }))
  }

  function changerContact(index, cle, valeur) {
    setBrouillon((b) => ({
      ...b,
      contacts: b.contacts.map((c, i) => (i === index ? { ...c, [cle]: valeur } : c)),
    }))
  }

  function basculerCours(coursId) {
    setBrouillon((b) => ({
      ...b,
      coursIds: b.coursIds.includes(coursId) ? b.coursIds.filter((id) => id !== coursId) : [...b.coursIds, coursId],
    }))
  }

  async function valider() {
    setEnCours(true)
    setErreur('')
    try {
      // Cours et contacts d'abord, la fiche elle-même en dernier : sa
      // réponse est l'élève à jour, avec ses cours et ses contacts.
      const coursChanges = cours
        .map((c) => c.id)
        .filter((id) => eleve.coursIds.includes(id) !== brouillon.coursIds.includes(id))
      for (const coursId of coursChanges) await elevesApi.basculerCours(eleve.id, coursId)

      const gardes = new Set(brouillon.contacts.filter((c) => c.id).map((c) => c.id))
      for (const ancien of eleve.contactsEleve) {
        if (!gardes.has(ancien.id)) await elevesApi.supprimerContact(eleve.id, ancien.id)
      }
      for (const contact of brouillon.contacts) {
        const champs = {
          prenom: contact.prenom ?? '',
          nom: contact.nom ?? '',
          lien: contact.lien ?? '',
          telephone: contact.telephone ?? '',
          email: contact.email ?? '',
        }
        if (!contact.id) {
          await elevesApi.ajouterContact(eleve.id, champs)
        } else {
          const avant = eleve.contactsEleve.find((c) => c.id === contact.id)
          if (Object.keys(champs).some((cle) => (avant[cle] ?? '') !== champs[cle])) {
            await elevesApi.modifierContact(eleve.id, contact.id, champs)
          }
        }
      }

      for (const { field, value } of reponses) {
        const nouvelle = brouillon.champs[field.id]
        if (field.format === 'file') {
          if (nouvelle instanceof File) await champsApi.envoyerFichier(eleve.id, field.id, nouvelle)
        } else if (JSON.stringify(nouvelle ?? null) !== JSON.stringify(value ?? null)) {
          await champsApi.repondre(eleve.id, field.id, nouvelle)
        }
      }
      setReponses(await champsApi.reponses(eleve.id))

      const misAJour = await elevesApi.modifier(eleve.id, {
        prenom: brouillon.prenom.trim(),
        nom: brouillon.nom.trim(),
        dateNaissance: brouillon.dateNaissance || null,
        telephone: brouillon.telephone,
        email: brouillon.email.trim(),
        adresse: brouillon.adresse,
        statutPaiement: brouillon.statutPaiement,
        montantTotalAnnee: Number(brouillon.montantTotalAnnee) || 0,
        montantPaye: Number(brouillon.montantPaye) || 0,
        commentaireAdmin: brouillon.commentaireAdmin,
        allergies: brouillon.allergies,
        traitementMedical: brouillon.traitementMedical,
        informationsImportantes: brouillon.informationsImportantes,
      })
      onEnregistre(misAJour)
      setBrouillon(null)
    } catch (e) {
      setErreur(e.message?.startsWith('«') ? e.message : 'L’enregistrement a échoué : vérifiez la connexion, puis réessayez.')
    } finally {
      setEnCours(false)
    }
  }

  const age = calculerAge(eleve.dateNaissance)
  const nomCours = (id) => cours.find((c) => c.id === id)?.nom

  const piedLecture = (
    <div className="fiche-eleve__boutons">
      {/* Une personne = une fiche (spec/core.md §4). */}
      <button type="button" className="btn btn--secondary" onClick={() => setFusionOuverte(true)}>
        Fusionner avec…
      </button>
      <button type="button" className="btn btn--primary" onClick={() => setBrouillon(brouillonDe(eleve, reponses))}>
        <Icon name="edit" size={16} /> Modifier
      </button>
    </div>
  )
  const piedEdition = (
    <div className="fiche-eleve__boutons">
      <button
        type="button"
        className="btn btn--secondary"
        disabled={enCours}
        onClick={() => {
          setBrouillon(null)
          setErreur('')
        }}
      >
        Annuler
      </button>
      <button
        type="button"
        className="btn btn--primary"
        disabled={enCours || !brouillon?.prenom.trim() || !brouillon?.nom.trim()}
        onClick={valider}
      >
        {enCours ? 'Enregistrement…' : 'Valider'}
      </button>
    </div>
  )

  if (fusionOuverte) {
    return <FusionnerAvec ecoleId={ecoleId} fiche={eleve} onClose={() => setFusionOuverte(false)} onFait={onFusionnee} />
  }

  return (
    <Modal
      title={`${eleve.prenom} ${eleve.nom}`}
      onClose={() => {
        if (!enEdition || window.confirm('Abandonner les modifications de la fiche ?')) onClose()
      }}
      footer={
        <>
          {erreur && <p className="login-screen__erreur">{erreur}</p>}
          {enEdition ? piedEdition : piedLecture}
        </>
      }
    >
      {enEdition ? (
        <div className="fiche-eleve form-fields">
          <Rubrique titre="Identité">
            <Saisie id="fiche-prenom" libelle="Prénom" valeur={brouillon.prenom} onChange={(v) => changer('prenom', v)} />
            <Saisie id="fiche-nom" libelle="Nom" valeur={brouillon.nom} onChange={(v) => changer('nom', v)} />
            <Saisie
              id="fiche-naissance"
              libelle="Date de naissance"
              type="date"
              valeur={brouillon.dateNaissance}
              onChange={(v) => changer('dateNaissance', v)}
            />
          </Rubrique>
          <Rubrique titre="Coordonnées">
            <Saisie
              id="fiche-telephone"
              libelle="Téléphone"
              type="tel"
              valeur={brouillon.telephone}
              onChange={(v) => changer('telephone', v)}
            />
            {/* Plusieurs emails possibles (§2.1) : chacun permet de se
                connecter, et relie la fiche aux autres qui l'ont. */}
            <label htmlFor="fiche-email">Emails</label>
            <ListeEmails id="fiche-email" valeur={brouillon.email} onChange={(v) => changer('email', v)} />
            <Saisie id="fiche-adresse" libelle="Adresse" valeur={brouillon.adresse} onChange={(v) => changer('adresse', v)} />
          </Rubrique>
          <Rubrique titre="Cours suivis">
            <div className="checkbox-list">
              {cours.map((c) => (
                <label key={c.id} className="checkbox-list__item">
                  <input type="checkbox" checked={brouillon.coursIds.includes(c.id)} onChange={() => basculerCours(c.id)} />
                  {c.nom}
                </label>
              ))}
            </div>
          </Rubrique>
          <Rubrique titre="Paiement">
            <label htmlFor="fiche-statut">Statut</label>
            <select
              id="fiche-statut"
              className="field-input"
              value={brouillon.statutPaiement}
              onChange={(e) => changer('statutPaiement', e.target.value)}
            >
              {Object.entries(paiementLabels).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
            <Saisie
              id="fiche-total"
              libelle="Montant total de l’année (€)"
              type="number"
              valeur={brouillon.montantTotalAnnee}
              onChange={(v) => changer('montantTotalAnnee', v)}
            />
            <Saisie
              id="fiche-paye"
              libelle="Montant payé (€)"
              type="number"
              valeur={brouillon.montantPaye}
              onChange={(v) => changer('montantPaye', v)}
            />
          </Rubrique>
          <Rubrique titre="Contacts">
            {brouillon.contacts.map((c, i) => (
              <div key={c.id ?? `nouveau-${i}`} className="contacts-eleve-list__item">
                <div className="contacts-eleve-list__row">
                  <input
                    className="field-input"
                    placeholder="Prénom"
                    value={c.prenom ?? ''}
                    onChange={(e) => changerContact(i, 'prenom', e.target.value)}
                  />
                  <input
                    className="field-input"
                    placeholder="Nom"
                    value={c.nom ?? ''}
                    onChange={(e) => changerContact(i, 'nom', e.target.value)}
                  />
                  <button
                    type="button"
                    className="icon-btn icon-btn--danger"
                    onClick={() => changer('contacts', brouillon.contacts.filter((_, j) => j !== i))}
                    aria-label="Retirer ce contact"
                  >
                    <Icon name="trash" size={16} />
                  </button>
                </div>
                <input
                  className="field-input"
                  placeholder="Lien (ex. Mère, Père...)"
                  value={c.lien ?? ''}
                  onChange={(e) => changerContact(i, 'lien', e.target.value)}
                />
                <input
                  className="field-input"
                  type="tel"
                  placeholder="Téléphone"
                  value={c.telephone ?? ''}
                  onChange={(e) => changerContact(i, 'telephone', e.target.value)}
                />
                <input
                  className="field-input"
                  type="email"
                  placeholder="Email"
                  value={c.email ?? ''}
                  onChange={(e) => changerContact(i, 'email', e.target.value)}
                />
              </div>
            ))}
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() =>
                changer('contacts', [
                  ...brouillon.contacts,
                  { id: null, prenom: '', nom: brouillon.nom, lien: '', telephone: '', email: '' },
                ])
              }
            >
              <Icon name="plus" size={16} /> Ajouter un contact
            </button>
          </Rubrique>
          <Rubrique titre="Santé">
            <ZoneTexte
              id="fiche-allergies"
              libelle="Allergies"
              valeur={brouillon.allergies}
              onChange={(v) => changer('allergies', v)}
            />
            <ZoneTexte
              id="fiche-traitement"
              libelle="Traitement médical"
              valeur={brouillon.traitementMedical}
              onChange={(v) => changer('traitementMedical', v)}
            />
            <ZoneTexte
              id="fiche-infos"
              libelle="Informations importantes"
              valeur={brouillon.informationsImportantes}
              onChange={(v) => changer('informationsImportantes', v)}
            />
          </Rubrique>
          {reponses.length > 0 && (
            <Rubrique titre="Nos champs">
              {reponses.map(({ field }) => (
                <SaisieChamp
                  key={field.id}
                  champ={field}
                  valeur={brouillon.champs[field.id]}
                  sousGroupes={sousGroupes[field.group_id] ?? []}
                  onChange={(v) => changerChamp(field.id, v)}
                />
              ))}
            </Rubrique>
          )}
          <Rubrique titre="Commentaire (réservé à l’admin)">
            <ZoneTexte
              id="fiche-commentaire"
              libelle="Commentaire"
              valeur={brouillon.commentaireAdmin}
              onChange={(v) => changer('commentaireAdmin', v)}
            />
          </Rubrique>
        </div>
      ) : (
        <div className="fiche-eleve">
          <Rubrique titre="Identité">
            <Ligne libelle="Prénom" valeur={eleve.prenom} />
            <Ligne libelle="Nom" valeur={eleve.nom} />
            <Ligne
              libelle="Date de naissance"
              valeur={eleve.dateNaissance && `${dateFrancaise(eleve.dateNaissance)}${age != null ? ` (${age} ans)` : ''}`}
            />
          </Rubrique>
          <Rubrique titre="Coordonnées">
            <Ligne libelle="Téléphone" valeur={eleve.telephone} />
            <Ligne libelle={eleve.emails?.length > 1 ? 'Emails' : 'Email'} valeur={eleve.email} />
            <Ligne libelle="Adresse" valeur={eleve.adresse} />
          </Rubrique>
          <Rubrique titre="Cours suivis">
            <Ligne valeur={eleve.coursIds.map(nomCours).filter(Boolean).join(', ')} />
          </Rubrique>
          <Rubrique titre="Paiement">
            <Ligne
              valeur={`${paiementLabels[eleve.statutPaiement]} — ${eleve.montantPaye} € payés sur ${eleve.montantTotalAnnee} €`}
            />
          </Rubrique>
          <Rubrique titre="Contacts">
            {eleve.contactsEleve.length === 0 && <Ligne valeur="" />}
            {eleve.contactsEleve.map((c) => (
              <Ligne
                key={c.id}
                libelle={[c.prenom, c.nom].filter(Boolean).join(' ') + (c.lien ? ` (${c.lien})` : '')}
                valeur={[c.telephone, c.email].filter(Boolean).join(' · ')}
              />
            ))}
          </Rubrique>
          <Rubrique titre="Santé">
            <Ligne libelle="Allergies" valeur={eleve.allergies} />
            <Ligne libelle="Traitement médical" valeur={eleve.traitementMedical} />
            <Ligne libelle="Informations importantes" valeur={eleve.informationsImportantes} />
          </Rubrique>
          {reponses.length > 0 && (
            <Rubrique titre="Nos champs">
              {reponses.map(({ field, value }) => (
                <Ligne
                  key={field.id}
                  libelle={field.label}
                  valeur={
                    field.format === 'file' && value ? (
                      <button
                        type="button"
                        className="champs__lien"
                        onClick={async () => window.open(await champsApi.urlFichier(eleve.id, field.id), '_blank')}
                      >
                        {value.name}
                      </button>
                    ) : (
                      texteReponse(field, value, sousGroupes[field.group_id] ?? [])
                    )
                  }
                />
              ))}
            </Rubrique>
          )}
          <Rubrique titre="Commentaire (réservé à l’admin)">
            <Ligne valeur={eleve.commentaireAdmin} />
          </Rubrique>
        </div>
      )}
    </Modal>
  )
}

function Rubrique({ titre, children }) {
  return (
    <section className="fiche-eleve__rubrique">
      <h3 className="fiche-eleve__titre">{titre}</h3>
      {children}
    </section>
  )
}

function Ligne({ libelle, valeur }) {
  return (
    <div className="fiche-eleve__ligne">
      {libelle && <span className="muted">{libelle}</span>}
      <span>{valeur || <span className="muted">—</span>}</span>
    </div>
  )
}

function Saisie({ id, libelle, valeur, onChange, type = 'text' }) {
  return (
    <>
      <label htmlFor={id}>{libelle}</label>
      <input id={id} className="field-input" type={type} value={valeur} onChange={(e) => onChange(e.target.value)} />
    </>
  )
}

function ZoneTexte({ id, libelle, valeur, onChange }) {
  return (
    <>
      <label htmlFor={id}>{libelle}</label>
      <textarea id={id} className="modal-textarea" rows={2} value={valeur} onChange={(e) => onChange(e.target.value)} />
    </>
  )
}

// La saisie d'un champ de l'école, selon son format.
function SaisieChamp({ champ, valeur, sousGroupes, onChange }) {
  const id = `fiche-champ-${champ.id}`
  const libelle = champ.label
  switch (champ.format) {
    case 'long_text':
      return <ZoneTexte id={id} libelle={libelle} valeur={valeur ?? ''} onChange={onChange} />
    case 'number':
      return <Saisie id={id} libelle={libelle} type="number" valeur={valeur ?? ''} onChange={onChange} />
    case 'date':
      return <Saisie id={id} libelle={libelle} type="date" valeur={valeur ?? ''} onChange={onChange} />
    case 'phone':
      return <Saisie id={id} libelle={libelle} type="tel" valeur={valeur ?? ''} onChange={onChange} />
    case 'yes_no':
      return (
        <label className="champs__case">
          <input type="checkbox" checked={valeur === true} onChange={(e) => onChange(e.target.checked)} />
          {libelle}
        </label>
      )
    case 'file':
      return (
        <>
          <label htmlFor={id}>{libelle}</label>
          <div className="champs__fichier">
            {valeur && !(valeur instanceof File) && <span>{valeur.name}</span>}
            <input id={id} type="file" onChange={(e) => onChange(e.target.files[0] ?? valeur)} />
          </div>
        </>
      )
    case 'list':
    case 'group': {
      const options =
        champ.format === 'list' ? champ.choices.map((c) => ({ id: c, name: c })) : sousGroupes
      if (champ.multiple) {
        const coches = valeur ?? []
        return (
          <>
            <label>{libelle}</label>
            <div className="checkbox-list">
              {options.map((o) => (
                <label key={o.id} className="checkbox-list__item">
                  <input
                    type="checkbox"
                    checked={coches.includes(o.id)}
                    onChange={() =>
                      onChange(coches.includes(o.id) ? coches.filter((x) => x !== o.id) : [...coches, o.id])
                    }
                  />
                  {o.name}
                </label>
              ))}
            </div>
          </>
        )
      }
      const choisi = champ.format === 'group' ? (valeur ?? [])[0] : valeur
      return (
        <>
          <label htmlFor={id}>{libelle}</label>
          <select
            id={id}
            className="field-input"
            value={choisi ?? ''}
            onChange={(e) => {
              const brut = e.target.value
              if (champ.format === 'group') onChange(brut ? [Number(brut)] : [])
              else onChange(brut || null)
            }}
          >
            <option value="">—</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </>
      )
    }
    default:
      return <Saisie id={id} libelle={libelle} valeur={valeur ?? ''} onChange={onChange} />
  }
}
