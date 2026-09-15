import { useState } from 'react'
import * as elevesApi from '../../api/eleves.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

const LIBELLE_CHAMP = {
  email: 'Email',
  telephone: 'Téléphone',
  adresse: 'Adresse',
  date_naissance: 'Date de naissance',
  cours: 'Cours',
}

function nomsCours(ids, cours) {
  return ids.map((id) => cours.find((c) => c.id === id)?.nom).filter(Boolean).join(', ')
}

function formaterValeur(champ, valeur, cours) {
  if (valeur == null || valeur === '' || (Array.isArray(valeur) && valeur.length === 0)) {
    return '(vide)'
  }
  return champ === 'cours' ? nomsCours(valeur, cours) : String(valeur)
}

// Modale PARTAGÉE entre Admin > École ("Intégrer fichier élèves officiel")
// et Admin > Élèves ("Importer") — demande utilisateur explicite : "c'est
// la meme fonction, appelable de 2 endroits", jamais 2 implémentations.
// Voir spec/SPEC.md §6.4bis et backend/src/eleves/import_excel.py.
export default function IntegrerFichierElevesModal({ ecoleId, cours, setEleves, onClose }) {
  const [fichier, setFichier] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [apercu, setApercu] = useState(null) // { colonnes_non_reconnues_globales }
  const [lignes, setLignes] = useState([]) // copie de travail, ajustable par l'admin
  const [mappingChoix, setMappingChoix] = useState({}) // { [colonne]: coursId }
  const [enCoursValidation, setEnCoursValidation] = useState(false)
  const [resultat, setResultat] = useState(null)

  async function analyser(f) {
    setChargement(true)
    setErreur(null)
    try {
      const a = await elevesApi.previsualiserImport(ecoleId, f)
      setApercu(a)
      setLignes(a.lignes)
      setFichier(f)
    } catch (err) {
      setErreur(err.message)
    } finally {
      setChargement(false)
    }
  }

  async function associerColonne(colonne) {
    const coursId = mappingChoix[colonne]
    if (!coursId) return
    setErreur(null)
    try {
      await elevesApi.memoriserMappingColonne(ecoleId, colonne, Number(coursId))
      await analyser(fichier) // ré-analyse le même fichier, colonne maintenant résolue
    } catch (err) {
      setErreur(err.message)
    }
  }

  function toggleCreer(numeroLigne) {
    setLignes((ls) => ls.map((l) => (l.numero_ligne === numeroLigne ? { ...l, creer: !l.creer } : l)))
  }

  function definirChampAAppliquer(numeroLigne, champ, appliquer) {
    setLignes((ls) =>
      ls.map((l) => {
        if (l.numero_ligne !== numeroLigne) return l
        const champs = l.champs_a_appliquer.filter((c) => c !== champ)
        return { ...l, champs_a_appliquer: appliquer ? [...champs, champ] : champs }
      }),
    )
  }

  async function valider() {
    if (enCoursValidation) return
    setEnCoursValidation(true)
    setErreur(null)
    try {
      const r = await elevesApi.validerImport(ecoleId, lignes)
      setResultat(r)
      setEleves(await elevesApi.lister(ecoleId))
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCoursValidation(false)
    }
  }

  if (resultat) {
    return (
      <Modal title="Intégration terminée" onClose={onClose}>
        <p>
          <Icon name="check" size={16} /> {resultat.crees} nouveau(x) élève(s) créé(s), {resultat.mis_a_jour} mis
          à jour, {resultat.inchanges} déjà à jour.
        </p>
        <button type="button" className="btn btn--primary btn--block" onClick={onClose}>
          Fermer
        </button>
      </Modal>
    )
  }

  if (!apercu) {
    return (
      <Modal title="Intégrer fichier élèves officiel" onClose={onClose}>
        <p className="muted">
          Sélectionnez un fichier <strong>.csv</strong>, ou un classeur <strong>Excel (.xlsx)</strong> — seul
          le 1er onglet est lu. Les 2 premières colonnes doivent être le nom et le prénom de l'élève (ex.
          "Nom adhérent", "Prénom adhérent", ou équivalent).
        </p>
        <input
          type="file"
          accept=".csv,.xlsx"
          disabled={chargement}
          onChange={(e) => {
            const f = e.target.files[0]
            if (f) analyser(f)
          }}
        />
        {chargement && <p className="muted">Analyse du fichier…</p>}
        {erreur && <p className="admin-panel__erreur">{erreur}</p>}
      </Modal>
    )
  }

  const nouveaux = lignes.filter((l) => l.eleve_existant_id == null)
  const existantsAvecDiff = lignes.filter((l) => l.eleve_existant_id != null && l.differences.length > 0)
  const inchangesCount = lignes.length - nouveaux.length - existantsAvecDiff.length

  return (
    <Modal
      title="Intégrer fichier élèves officiel"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={enCoursValidation}
          onClick={valider}
        >
          Valider l'import
        </button>
      }
    >
      <div className="import-eleves__resume">
        <span className="muted">
          {nouveaux.length} nouveau(x), {existantsAvecDiff.length} avec différence(s), {inchangesCount} déjà
          à jour.
        </span>
      </div>

      {apercu.colonnes_non_reconnues_globales.length > 0 && (
        <div className="import-eleves__mapping">
          <p className="muted">
            Colonnes non reconnues — associez chacune à un cours pour qu'elle soit prise en compte
            (mémorisé pour les prochains imports) :
          </p>
          {apercu.colonnes_non_reconnues_globales.map((colonne) => (
            <div key={colonne} className="import-eleves__mapping-ligne">
              <span>{colonne}</span>
              <select
                className="field-input"
                value={mappingChoix[colonne] ?? ''}
                onChange={(e) => setMappingChoix((m) => ({ ...m, [colonne]: e.target.value }))}
              >
                <option value="">Choisir un cours…</option>
                {cours.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nom}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn--secondary"
                disabled={!mappingChoix[colonne] || chargement}
                onClick={() => associerColonne(colonne)}
              >
                Associer
              </button>
            </div>
          ))}
        </div>
      )}

      {nouveaux.length > 0 && (
        <>
          <p className="import-eleves__section-titre">Nouveaux élèves ({nouveaux.length})</p>
          <div className="checkbox-list">
            {nouveaux.map((l) => (
              <label key={l.numero_ligne} className="checkbox-list__item">
                <input type="checkbox" checked={l.creer} onChange={() => toggleCreer(l.numero_ligne)} />
                <span>
                  {l.prenom} {l.nom}
                  {l.cours_ids.length > 0 && ` — ${nomsCours(l.cours_ids, cours)}`}
                  {l.telephone_suspect && (
                    <span className="import-eleves__avertissement"> ⚠ téléphone à vérifier</span>
                  )}
                  {l.ambigu && (
                    <span className="import-eleves__avertissement">
                      {' '}
                      ⚠ plusieurs élèves portent déjà ce nom — vérifiez avant de créer un doublon
                    </span>
                  )}
                  {l.doublon_fichier && (
                    <span className="import-eleves__avertissement">
                      {' '}
                      ⚠ ce nom apparaît plusieurs fois dans le fichier — choisissez laquelle garder
                    </span>
                  )}
                </span>
              </label>
            ))}
          </div>
        </>
      )}

      {existantsAvecDiff.length > 0 && (
        <>
          <p className="import-eleves__section-titre">
            Élèves existants avec différences ({existantsAvecDiff.length})
          </p>
          <div className="contacts-eleve-list">
            {existantsAvecDiff.map((l) => (
              <div key={l.numero_ligne} className="contacts-eleve-list__item">
                <strong>
                  {l.prenom} {l.nom}
                </strong>
                {l.differences.map((d) => {
                  const applique = l.champs_a_appliquer.includes(d.champ)
                  const nomGroupe = `diff-${l.numero_ligne}-${d.champ}`
                  return (
                    <div key={d.champ} className="import-eleves__difference">
                      <span className="import-eleves__difference-label">{LIBELLE_CHAMP[d.champ]}</span>
                      <label>
                        <input
                          type="radio"
                          name={nomGroupe}
                          checked={!applique}
                          onChange={() => definirChampAAppliquer(l.numero_ligne, d.champ, false)}
                        />
                        Garder : {formaterValeur(d.champ, d.valeur_actuelle, cours)}
                      </label>
                      <label>
                        <input
                          type="radio"
                          name={nomGroupe}
                          checked={applique}
                          onChange={() => definirChampAAppliquer(l.numero_ligne, d.champ, true)}
                        />
                        Utiliser le fichier : {formaterValeur(d.champ, d.valeur_fichier, cours)}
                      </label>
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </>
      )}

      {erreur && <p className="admin-panel__erreur">{erreur}</p>}
    </Modal>
  )
}
