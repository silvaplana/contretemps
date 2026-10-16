import { useMemo, useState } from 'react'
import qrcode from 'qrcode-generator'
import { useApparence } from '../../../api/apparence.js'
import { adresseDeLaPage } from '../../../pagePublique/hote.js'
import DiffuserChoisis from './DiffuserChoisis.jsx'

// Onglet Diffuser (fichier-de-base.md §2.3). « Tout le monde » : la page en
// ligne (documents.md §5.5), en Officiel seulement (en Validé, on diffuse aux
// relecteurs : décision de Seb du 16 octobre). « Des personnes choisies » :
// emails avec lien personnel (DiffuserChoisis) ; SMS et relances ensuite.

function Qr({ texte }) {
  const { n, cases } = useMemo(() => {
    const qr = qrcode(0, 'M')
    qr.addData(texte)
    qr.make()
    const taille = qr.getModuleCount()
    const noires = []
    for (let y = 0; y < taille; y += 1) for (let x = 0; x < taille; x += 1) if (qr.isDark(y, x)) noires.push(`M${x} ${y}h1v1h-1z`)
    return { n: taille, cases: noires.join('') }
  }, [texte])
  return (
    <svg className="ad-qr" viewBox={`-2 -2 ${n + 4} ${n + 4}`} role="img" aria-label={`QR code de ${texte}`} shapeRendering="crispEdges">
      <rect x="-2" y="-2" width={n + 4} height={n + 4} fill="#fff" />
      <path d={cases} fill="#000" />
    </svg>
  )
}

export default function Diffuser({ file, api, onToast, onChanged }) {
  const apparence = useApparence()
  const [confirmer, setConfirmer] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const pub = file.publication
  const enLigne = Boolean(pub?.online)
  const adresse = pub ? adresseDeLaPage(apparence.adresse, pub.slug) : null
  const raison = !file.can_manage
    ? 'Un admin met la page en ligne'
    : file.space === 'personal'
      ? 'Un fichier de l’espace Personnel ne se met pas en ligne'
      : file.status !== 'official'
        ? 'Passez le fichier en Officiel pour l’ouvrir à tout le monde'
        : null

  async function faire(action, message) {
    setEnCours(true)
    try {
      await action()
      await onChanged()
      onToast(message)
    } catch (e) {
      onToast(e.message)
    } finally {
      setEnCours(false)
      setConfirmer(false)
    }
  }

  // En Validé, on fait relire d'abord : la carte vient en tête.
  const choisis = <DiffuserChoisis file={file} api={api} onToast={onToast} />
  return (
    <div className="ad">
      {file.status === 'validated' && choisis}
      <section className="ad-carte">
        <h3>Tout le monde</h3>
        {enLigne ? (
          <>
            <p className="ad-etat">
              <span className="ad-pastille" aria-hidden="true" /> En ligne
              {pub.visits > 0 && <span className="ad-vues"> · {pub.visits} visite{pub.visits > 1 ? 's' : ''}</span>}
            </p>
            {adresse ? (
              <>
                <a className="ad-adresse" href={adresse} target="_blank" rel="noopener noreferrer">{adresse.replace('https://', '')}</a>
                <div className="ad-boutons">
                  <button
                    type="button"
                    className="dx-btn dx-btn--small"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(adresse)
                        onToast('Adresse copiée')
                      } catch {
                        onToast(adresse)
                      }
                    }}
                  >
                    Copier l’adresse
                  </button>
                </div>
                <Qr texte={adresse} />
                <p className="af-hint">Le QR code se met sur l’affiche ou le flyer : on le vise avec le téléphone.</p>
              </>
            ) : (
              <p className="af-hint">Nom de la page : {pub.slug} (l’adresse complète s’affiche sur l’adresse de l’école).</p>
            )}
            {file.can_manage && (
              <button type="button" className="ad-retirer" disabled={enCours} onClick={() => faire(() => api.unpublish(file.id), 'Page retirée d’internet')}>
                Retirer d’internet
              </button>
            )}
          </>
        ) : confirmer ? (
          <>
            <p className="ad-attention">Visible par tout le monde sur internet, sans compte. {file.family !== 'inform' && 'Chacun pourra répondre.'}</p>
            <div className="ad-boutons">
              <button type="button" className="dx-btn" disabled={enCours} onClick={() => faire(() => api.publish(file.id), 'La page est en ligne')}>
                Mettre en ligne
              </button>
              <button type="button" className="dx-btn dx-btn--ghost" onClick={() => setConfirmer(false)}>Annuler</button>
            </div>
          </>
        ) : (
          <>
            <p className="af-hint">
              Une adresse web à partager ou à mettre en QR code sur une affiche{file.family !== 'inform' ? ' : chacun répond sans compte, les réponses arrivent dans Résultats' : ''}.
              {pub && ' La page avait été retirée : elle reprendra la même adresse.'}
            </p>
            <button type="button" className="dx-btn" disabled={Boolean(raison)} onClick={() => setConfirmer(true)}>
              Mettre en ligne
            </button>
            {raison && <p className="ad-raison">{raison}.</p>}
          </>
        )}
      </section>

      {file.status !== 'validated' && choisis}
    </div>
  )
}
