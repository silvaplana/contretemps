import { useEffect, useState } from 'react'
import * as ecolesApi from '../../api/ecoles.js'
import Icon from '../../components/Icon.jsx'
import { useSaisonConsultee } from '../../api/saison.js'
import AdministrateursTableau from './AdministrateursTableau.jsx'
import { isOwner } from '../../data/roles.js'
import SaisonsSection from './SaisonsSection.jsx'
import SauvegardeEcoleMenu from './SauvegardeEcoleMenu.jsx'
import PersonnalisationSection from './PersonnalisationSection.jsx'
import UsageVideoSection from './UsageVideoSection.jsx'

// Onglet Admin > École (voir spec/SPEC.md §5.1.1 et §6.1) : nom de l'école
// et code postal, modifiables par tout admin (plus de codes d'accès depuis
// le 2026-10-01, §2.2). Premier sous-onglet, le plus à gauche.
// Le code postal distingue deux écoles qui porteraient le même nom (le
// couple nom + code postal doit être unique, pas le nom seul).
//
// Persisté via api/ecoles.js (voir api/README.md) — avant, `update` ne
// touchait qu'à l'état React local (setEcole), jamais sauvegardé : toute
// modif disparaissait à la fermeture de l'appli (bug signalé, ex. code
// postal). Chaque champ appelle l'API à chaque frappe, comme les autres
// écrans Admin (voir AdminEleves.jsx : EditableText/update) — mais MAJ
// locale immédiate (optimiste), sans attendre la réponse réseau pour
// mettre à jour l'affichage : sur ces champs texte, attendre la réponse
// avant de raffraîchir `ecole` peut faire résoudre les requêtes dans le
// désordre (une frappe rapide envoie plusieurs PUT qui ne reviennent pas
// forcément dans l'ordre d'envoi) et faire revenir l'affichage en
// arrière au milieu de la frappe. La persistance reste garantie : chaque
// requête envoie la valeur complète du champ à cet instant, la dernière
// envoyée finit par gagner côté serveur.
//
// Menu ⋮ dans l'en-tête, à droite du badge de l'utilisateur (demande du
// 2026-09-21, voir SauvegardeEcoleMenu.jsx) : sauvegarder/programmer/
// importer/supprimer les données de l'école, le téléchargement des
// nouvelles inscriptions et, pour un administrateur principal, "Ajouter un
// administrateur" (un seul ⋮ pour tout l'écran).
export default function AdminParametres({
  ecole,
  setEcole,
  choregraphies,
  setChoregraphies,
  cours,
  eleves,
  setEleves,
  activeUser,
  professeurs,
  onSaisonCreee,
  onSaisonSupprimee,
}) {
  const [creationAdminOuverte, setCreationAdminOuverte] = useState(false)
  const [coordonneesOuvertes, setCoordonneesOuvertes] = useState(false)
  const saisonConsultee = useSaisonConsultee()

  // Réglages de sauvegarde : chargés ici, par la route réservée aux
  // admins (voir api/ecoles.js : obtenir). L'école reçue à la connexion
  // n'a que son nom et son code postal.
  useEffect(() => {
    let annule = false
    ecolesApi
      .obtenir(ecole.id)
      .then((complete) => {
        if (!annule) setEcole((e) => ({ ...e, ...complete }))
      })
      .catch((err) => console.error(err))
    return () => {
      annule = true
    }
  }, [ecole.id, setEcole])

  function update(patch) {
    setEcole((e) => ({ ...e, ...patch }))
    ecolesApi.modifier(ecole.id, patch).catch((err) => console.error(err))
  }

  // SIRET, IBAN : vérifiés par le serveur, enregistrés en quittant le champ
  // (pas à chaque touche, qui serait refusée tant que la saisie n'est pas
  // finie). Lève l'erreur du serveur, affichée sous le champ.
  async function enregistrerVerifie(patch) {
    const complete = await ecolesApi.modifier(ecole.id, patch)
    setEcole((e) => ({ ...e, siret: complete.siret, iban: complete.iban }))
  }

  return (
    <div className="admin-panel admin-panel--ecole">
      <SauvegardeEcoleMenu
        ecole={ecole}
        cours={cours}
        setEleves={setEleves}
        onAjouterAdministrateur={isOwner(activeUser) ? () => setCreationAdminOuverte(true) : null}
      />

      {/* Premier volet dépliable (demande du 2026-10-15) : nom, code
          postal et coordonnées imprimées sur les documents. */}
      <section className="admin-coordonnees">
        <h3 className="section-label">
          <button
            type="button"
            className="section-label__depliant"
            aria-expanded={coordonneesOuvertes}
            onClick={() => setCoordonneesOuvertes((o) => !o)}
          >
            <Icon name={coordonneesOuvertes ? 'chevronDown' : 'chevronRight'} size={14} />
            Coordonnées
          </button>
        </h3>
        {coordonneesOuvertes && (
          <div className="form-fields">
            <label htmlFor="ecole-param-nom">Nom de l’école</label>
            <input
              id="ecole-param-nom"
              className="field-input"
              value={ecole.nom}
              onChange={(e) => update({ nom: e.target.value })}
            />

            <label htmlFor="ecole-param-cp">Code postal</label>
            <input
              id="ecole-param-cp"
              className="field-input"
              value={ecole.codePostal}
              onChange={(e) => update({ codePostal: e.target.value })}
            />

            {/* Coordonnées (spec §6.1, demande du 2026-10-15) : imprimées sur la
                facture et le dossier d'inscription à la place des valeurs par
                défaut. */}
            <label htmlFor="ecole-param-adresse">Adresse</label>
            <textarea
              id="ecole-param-adresse"
              className="field-input"
              rows={2}
              value={ecole.adresse ?? ''}
              placeholder="Numéro et rue"
              onChange={(e) => update({ adresse: e.target.value })}
            />

            <label htmlFor="ecole-param-ville">Ville</label>
            <input
              id="ecole-param-ville"
              className="field-input"
              value={ecole.ville ?? ''}
              onChange={(e) => update({ ville: e.target.value })}
            />

            <ChampVerifie
              id="ecole-param-siret"
              label="SIRET"
              placeholder="123 456 789 00012"
              valeur={ecole.siret ?? ''}
              afficher={siretLisible}
              enregistrer={(siret) => enregistrerVerifie({ siret })}
            />

            <ChampVerifie
              id="ecole-param-iban"
              label="IBAN"
              placeholder="FR76 3000 6000 0112 3456 7890 189"
              valeur={ecole.iban ?? ''}
              afficher={ibanLisible}
              enregistrer={(iban) => enregistrerVerifie({ iban })}
            />
          </div>
        )}
      </section>

      {/* Sections au même niveau, même format de titre (demande du
          2026-09-21) : Saisons (spec §2.6, entre les codes d'accès et les
          administrateurs), Administrateurs (spec §2.4), puis Usage vidéo. */}
      <SaisonsSection
        key={activeUser.id}
        ecoleId={ecole.id}
        onSaisonCreee={onSaisonCreee}
        onSaisonSupprimee={onSaisonSupprimee}
      />

      <AdministrateursTableau
        ecoleId={ecole.id}
        activeUser={activeUser}
        professeurs={professeurs}
        eleves={eleves}
        creationOuverte={creationAdminOuverte}
        onFermerCreation={() => setCreationAdminOuverte(false)}
      />

      {/* `key` : recalculé quand la saison affichée change (spec §2.6). */}
      <UsageVideoSection key={saisonConsultee?.id ?? 'courante'} ecoleId={ecole.id}
        choregraphies={choregraphies}
        cours={cours}
        setChoregraphies={setChoregraphies}
      />

      {/* Dernier volet (demande du 2026-10-15) : apparence de l'appli et
          adresse web de l'école (spec §2.7, §5.1.1). */}
      <PersonnalisationSection ecole={ecole} activeUser={activeUser} />
    </div>
  )
}

// « 12345678900012 » -> « 123 456 789 00012 » (spec §6.1).
function siretLisible(siret) {
  return siret.length === 14 ? `${siret.slice(0, 3)} ${siret.slice(3, 6)} ${siret.slice(6, 9)} ${siret.slice(9)}` : siret
}

// IBAN par groupes de 4.
function ibanLisible(iban) {
  return iban.replace(/(.{4})/g, '$1 ').trim()
}

// Champ vérifié par le serveur (SIRET, IBAN) : saisie libre, enregistrée en
// quittant le champ ; l'erreur éventuelle reste affichée dessous.
function ChampVerifie({ id, label, placeholder, valeur, afficher, enregistrer }) {
  const [saisie, setSaisie] = useState(null) // null : pas en cours de saisie
  const [erreur, setErreur] = useState('')

  async function quitter() {
    if (saisie === null) return
    if (saisie.replace(/\s/g, '').toUpperCase() === valeur) {
      setSaisie(null)
      return
    }
    try {
      await enregistrer(saisie)
      setErreur('')
      setSaisie(null)
    } catch (err) {
      setErreur(err.message)
    }
  }

  return (
    <>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className="field-input"
        value={saisie ?? afficher(valeur)}
        placeholder={placeholder}
        onChange={(e) => setSaisie(e.target.value)}
        onBlur={quitter}
      />
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </>
  )
}
