import { useEffect, useState } from 'react'
import Page, { SignZone } from './Page.jsx'

// Document à signer, « 1. Préparer », Mode Aperçu (signature-documents.md
// §2.2) : le document tel qu'il sera signé. Un Word en Brouillon se corrige
// en touchant son texte ; un PDF (ou tout document figé) montre ses pages.

function Pages({ api, id, count, initials, version }) {
  const [urls, setUrls] = useState([])
  useEffect(() => {
    let actif = true
    const faites = []
    ;(async () => {
      for (let n = 1; n <= count; n += 1) {
        try {
          const image = await api.signingPage(id, n)
          if (!actif) break
          faites.push(URL.createObjectURL(image))
          setUrls([...faites])
        } catch {
          break
        }
      }
    })()
    return () => {
      actif = false
      faites.forEach((u) => URL.revokeObjectURL(u))
    }
  }, [api, id, count, version])
  return urls.map((url, i) => (
    <figure key={url} className="sg-page">
      <img src={url} alt={`Page ${i + 1} sur ${count}`} />
      {initials && <span className="sg-paraphe">Paraphe</span>}
    </figure>
  ))
}

export default function SignPreview({ file, content, block, sign, api, size, onTexte }) {
  const initials = block.props?.mode === 'initials'
  if (!sign?.source && !sign?.frozen) {
    return <p className="dx-note">Choisissez d’abord le document : Mode › Édition.</p>
  }
  const fige = sign.frozen
  return (
    <div className={`sg-apercu sg-apercu--${size}`}>
      {fige && (
        <p className="sg-seal">
          Figé le {new Date(fige.at).toLocaleDateString('fr-FR')} : plus rien ne change, seules les signatures s’ajouteront.
          <br />
          Empreinte : <code>{fige.sha256.slice(0, 10)}…{fige.sha256.slice(-6)}</code>
        </p>
      )}
      {sign.pages > 0 ? (
        <>
          <Pages api={api} id={file.id} count={sign.pages} initials={initials} version={fige?.sha256 ?? sign.source?.id} />
          <SignZone block={block} />
        </>
      ) : (
        <>
          {onTexte && <p className="af-hint af-hint--fort">Touchez un texte pour le corriger directement.</p>}
          <Page content={content} size={size} onTexte={onTexte} />
        </>
      )}
    </div>
  )
}
