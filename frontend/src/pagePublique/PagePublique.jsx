import { useEffect, useState } from 'react'
import { mettreAJour, urlLogo, useApparence, versEcran } from '../api/apparence.js'
import Page from '../modules/documents/app/Page.jsx'
import SignLink from '../modules/documents/app/SignLink.jsx'
import '../modules/documents/app/app.css'
import './pagePublique.css'

// La page en ligne d'un fichier de l'appli (documents.md §5.5,
// fichier-de-base.md §2.3) : le formulaire d'entrée, aux couleurs de
// l'école, rempli sans compte. Rien d'autre de l'appli n'est chargé.
// Aussi le lien personnel reçu par email (`<adresse de l'école>/r/<jeton>`) :
// même page, la réponse est celle de la personne et se corrige. Le lien d'un
// document à signer ouvre la page du signataire (signature-documents.md §2.4).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function lire(url, options) {
  const r = await fetch(url, options)
  if (!r.ok) {
    let message = 'Cette page ne répond pas. Réessayez plus tard.'
    try {
      const { detail } = await r.json()
      if (typeof detail === 'string') message = detail
    } catch {
      // pas de JSON : message par défaut
    }
    throw new Error(message)
  }
  return r.json()
}

// Convocation d'AG : le mail porte un lien par réponse (`?c=proxy`), la page
// s'ouvre avec ce choix déjà fait (procurations.md §1.1).
function choixDuMail(assembly) {
  const c = new URLSearchParams(window.location.search).get('c')
  return assembly && ['attend', 'proxy', 'absent'].includes(c) ? { [assembly.block_id]: { answer: c } } : undefined
}

export default function PagePublique({ slug, jeton }) {
  const apparence = useApparence()
  const [page, setPage] = useState(null)
  const [erreur, setErreur] = useState('')
  const [ecoleId, setEcoleId] = useState(null)
  const [envoiErreur, setEnvoiErreur] = useState('')

  useEffect(() => {
    ;(async () => {
      try {
        const vue = versEcran(await lire(`${BASE_URL}/par-host/personnalisation?host=${encodeURIComponent(window.location.host)}`))
        if (!vue.ecoleId && !jeton) throw new Error('Cette adresse ne correspond à aucune école.')
        if (vue.ecoleId) mettreAJour(vue)
        setEcoleId(vue.ecoleId)
        const p = await lire(
          jeton
            ? `${BASE_URL}/documents/public/links/${encodeURIComponent(jeton)}`
            : `${BASE_URL}/documents/public/orgs/${vue.ecoleId}/pages/${encodeURIComponent(slug)}`,
        )
        setPage(p)
        document.title = `${p.name} · ${vue.nom}`
      } catch (e) {
        setErreur(e.message)
      }
    })()
  }, [slug, jeton])

  async function repondre(values) {
    setEnvoiErreur('')
    try {
      const url = jeton
        ? `${BASE_URL}/documents/public/links/${encodeURIComponent(jeton)}/answers`
        : `${BASE_URL}/documents/public/orgs/${ecoleId}/pages/${encodeURIComponent(slug)}/answers`
      await lire(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values }),
      })
    } catch (e) {
      setEnvoiErreur(e.message)
      throw e
    }
  }

  return (
    <div className="pp">
      <header className="pp-haut">
        <img src={urlLogo(apparence)} alt="" />
        <span>{apparence.nom}</span>
      </header>
      <main className="pp-corps">
        {erreur && <p className="pp-erreur">{erreur}</p>}
        {!erreur && !page && <p className="pp-attente">Chargement…</p>}
        {page?.signing && <SignLink jeton={jeton} lire={lire} baseUrl={BASE_URL} />}
        {page && !page.signing && (
          <>
            {page.person && <p className="pp-note">Bonjour {page.person}{page.values ? ' : votre réponse est enregistrée, vous pouvez la corriger.' : ''}</p>}
            {page.trial && page.accepting && <p className="pp-note">Essai : votre réponse apparaîtra dans Résultats avec la mention « Essai », sans compter.</p>}
            {page.test && !page.trial && page.accepting && <p className="pp-note">Relecture : vos réponses sont des essais, elles ne comptent pas.</p>}
            {page.family !== 'inform' && !page.accepting && <p className="pp-note">Les réponses sont fermées.</p>}
            <Page
              content={page.content}
              size="phone"
              onSubmit={page.accepting ? repondre : undefined}
              initial={page.values ?? choixDuMail(page.assembly)}
              assembly={page.assembly ? { ...page.assembly, person: page.person } : undefined}
              submitLabel={page.signer ? 'Signer' : page.values ? 'Enregistrer ma réponse' : undefined}
            />
            {envoiErreur && <p className="pp-erreur" role="alert">{envoiErreur}</p>}
          </>
        )}
      </main>
    </div>
  )
}
