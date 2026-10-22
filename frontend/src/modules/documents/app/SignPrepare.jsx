import { useRef, useState } from 'react'

// Document à signer, « 1. Préparer », Mode Édition (signature-documents.md
// §2.1) : trois questions. Le document (un PDF ou un Word déposé, rangé dans
// le même dossier), où signer, ce que chacun doit savoir. Les réglages sont
// ceux du bloc `signDocument`, enregistrés comme tout fichier de l'appli.

export default function SignPrepare({ file, block, sign, api, onProps, onDocument, onToast }) {
  const p = block.props ?? {}
  const [envoi, setEnvoi] = useState(false)
  const entree = useRef(null)
  const doc = sign?.source
  const modifiable = file.editable

  async function deposer(e) {
    const choisi = e.target.files?.[0]
    e.target.value = ''
    if (!choisi) return
    setEnvoi(true)
    try {
      const depose = await api.upload(file.space, file.parent_id, choisi)
      await api.signingDocument(file.id, depose.id)
      await onDocument()
    } catch (err) {
      onToast(err.message)
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div className="sg">
      <section className="sg-q">
        <h3>1. Le document</h3>
        {doc && (
          <div className="sg-doc">
            <span className="sg-ico">{doc.kind === 'pdf' ? 'PDF' : 'DOC'}</span>
            <span>
              <b>{doc.name}</b>
              <small>{doc.kind === 'pdf' ? 'Un PDF ne se modifie pas.' : 'Son texte se corrige dans l’Aperçu.'}</small>
            </span>
          </div>
        )}
        {sign?.missing && <p className="dx-note">Le document choisi a été supprimé : déposez-le de nouveau.</p>}
        {modifiable && (
          <>
            <input ref={entree} type="file" accept=".pdf,.doc,.docx,.odt" hidden onChange={deposer} aria-label="Document à faire signer" />
            <button type="button" className="sg-drop" disabled={envoi} onClick={() => entree.current?.click()}>
              {envoi ? 'Envoi…' : doc ? 'Déposer un autre document' : 'Déposer un PDF ou un Word'}
              {!doc && !envoi && <small>Ou, dans Docs : ⋯ › Faire signer… sur le document</small>}
            </button>
          </>
        )}
      </section>

      <section className="sg-q" role="radiogroup" aria-label="Où signer ?">
        <h3>2. Où signer ?</h3>
        {[
          ['end', 'Une signature à la fin'],
          ['initials', 'Signature à la fin et paraphe en bas de chaque page'],
        ].map(([cle, texte]) => (
          <label key={cle} className={`sg-row${(p.mode || 'end') === cle ? ' sg-row--on' : ''}`}>
            <input type="radio" name="sg-mode" checked={(p.mode || 'end') === cle} disabled={!modifiable} onChange={() => onProps({ mode: cle })} />
            <span>{texte}</span>
          </label>
        ))}
      </section>

      <section className="sg-q">
        <h3>3. Ce que chacun doit savoir</h3>
        <label className="af-label" htmlFor="sg-mention">Mention écrite au-dessus de chaque signature</label>
        <input
          id="sg-mention"
          className="ap-input"
          maxLength={120}
          placeholder="Aucune"
          value={p.mention ?? ''}
          disabled={!modifiable}
          onChange={(e) => onProps({ mention: e.target.value })}
        />
        <label className="af-label" htmlFor="sg-message">Message aux signataires</label>
        <textarea
          id="sg-message"
          className="ap-input"
          rows={3}
          maxLength={2000}
          placeholder="Par exemple : merci de signer avant le 30 novembre."
          value={p.message ?? ''}
          disabled={!modifiable}
          onChange={(e) => onProps({ message: e.target.value })}
        />
      </section>
    </div>
  )
}
