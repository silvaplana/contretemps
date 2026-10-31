import { useEffect, useState } from 'react'
import * as comptesApi from '../../api/comptes.js'
import * as elevesApi from '../../api/eleves.js'
import * as profsApi from '../../api/profs.js'
import { compteEnCours } from '../../api/session.js'
import Modal from '../../components/Modal.jsx'
import { ROLE_LABEL } from '../../data/roles.js'
import { normaliserRecherche } from '../../utils/recherche.js'

// « Fusionner avec… » (spec/core.md §4, décision de Seb du 2026-10-18 : une
// personne = une fiche). On choisit l'autre fiche de la même personne ;
// celle qui reste reçoit ses rôles, emails, cours, messages, notes de frais
// et fichiers, l'autre disparaît. Les fiches au même nom viennent en tête.
export default function FusionnerAvec({ ecoleId, fiche, onClose, onFait }) {
  const [fiches, setFiches] = useState(null)
  const [choix, setChoix] = useState(null)
  // Les mails à garder (Seb, 31/10 : un des deux peut être faux) : rien de
  // coché d'avance, on demande.
  const [gardes, setGardes] = useState([])
  const [recherche, setRecherche] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    Promise.all([comptesApi.listerAdmins(ecoleId), profsApi.lister(ecoleId), elevesApi.lister(ecoleId)])
      .then(([admins, profs, eleves]) => {
        const parId = new Map()
        for (const [liste, role] of [
          [admins.filter((a) => a.role !== 'superuser'), 'admin'],
          [profs, 'professeur'],
          [eleves, 'eleve'],
        ]) {
          for (const c of liste) {
            const deja = parId.get(c.id) ?? { id: c.id, nom: c.nom, prenom: c.prenom, emails: mailsDe(c), roles: [] }
            deja.roles.push(role)
            parId.set(c.id, deja)
          }
        }
        parId.delete(fiche.id)
        setFiches([...parId.values()])
        // Une seule autre fiche au même nom : elle est déjà choisie.
        const memes = [...parId.values()].filter(
          (c) => normaliserRecherche(`${c.prenom} ${c.nom}`) === normaliserRecherche(`${fiche.prenom} ${fiche.nom}`),
        )
        if (memes.length === 1) choisir(memes[0])
      })
      .catch(() => setErreur('Impossible de charger les fiches.'))
  }, [ecoleId, fiche.id, fiche.prenom, fiche.nom])

  const memeNom = (c) => normaliserRecherche(`${c.prenom} ${c.nom}`) === normaliserRecherche(`${fiche.prenom} ${fiche.nom}`)
  const requete = normaliserRecherche(recherche.trim())
  const visibles = (fiches ?? [])
    .filter((c) => !requete || normaliserRecherche(`${c.prenom} ${c.nom}`).includes(requete))
    .sort((a, b) => memeNom(b) - memeNom(a) || `${a.prenom} ${a.nom}`.localeCompare(`${b.prenom} ${b.nom}`, 'fr'))

  function choisir(c) {
    setChoix(c)
    setGardes([])
  }
  const mails = choix ? [...new Set([...mailsDe(fiche), ...choix.emails])] : []
  const question = mails.length > 1
  const pret = choix && (!question || gardes.length > 0)

  async function fusionner() {
    if (!pret || enCours) return
    setEnCours(true)
    setErreur('')
    // Sa propre fiche reste toujours : sinon on se retrouverait déconnecté.
    const [garde, autre] = choix.id === Number(compteEnCours()) ? [choix.id, fiche.id] : [fiche.id, choix.id]
    try {
      await comptesApi.fusionner(garde, autre, question ? mails.filter((m) => gardes.includes(m)) : null)
      window.dispatchEvent(new Event('contretemps:donnees-modifiees'))
      onFait()
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Modal
      title="Fusionner avec…"
      onClose={onClose}
      footer={
        <>
          {erreur && <p className="login-screen__erreur">{erreur}</p>}
          <button type="button" className="btn btn--primary btn--block" disabled={!pret || enCours} onClick={fusionner}>
            {enCours
              ? 'Fusion…'
              : !choix
                ? 'Choisissez une fiche'
                : pret
                  ? `Fusionner avec ${choix.prenom} ${choix.nom}`
                  : 'Cochez le mail à garder'}
          </button>
        </>
      }
    >
      <p className="muted">
        Choisissez l'autre fiche de {fiche.prenom} {fiche.nom}. Il ne restera qu'une fiche, avec tout ce qu'avaient
        les deux : rôles, cours, messages.
      </p>
      {question && (
        <>
          <p className="fusion__question">Quel mail garder ?</p>
          <div className="checkbox-list">
            {mails.map((m) => (
              <label key={m} className="checkbox-list__item">
                <input
                  type="checkbox"
                  checked={gardes.includes(m)}
                  onChange={(e) => setGardes(e.target.checked ? [...gardes, m] : gardes.filter((g) => g !== m))}
                />
                {m}
              </label>
            ))}
          </div>
        </>
      )}
      <input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher" />
      {fiches === null && !erreur && <p className="muted">Chargement…</p>}
      <div className="checkbox-list">
        {visibles.map((c) => (
          <label key={c.id} className="checkbox-list__item">
            <input type="radio" name="fusion" checked={choix?.id === c.id} onChange={() => choisir(c)} />
            {c.prenom} {c.nom} <span className="muted">· {c.roles.map((r) => ROLE_LABEL[r]).join(', ')}</span>
          </label>
        ))}
      </div>
    </Modal>
  )
}

// Les mails d'une fiche : la liste `emails` quand l'API la donne, sinon le
// texte `email` (« a, b »).
function mailsDe(c) {
  return c.emails?.length ? c.emails : (c.email ?? '').split(/[,;\s]+/).filter(Boolean)
}
