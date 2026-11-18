import { dateComplete } from './format.js'

// Brouillon d'une réponse, d'une réponse à tous ou d'un transfert
// (spec/modules/mail.md §7), repris de Sambo Admin (Webmail.jsx, draftFrom).

// Adresse prête pour un champ « À » : "Nom" <adresse>.
function champ(personne) {
  if (!personne.name) return personne.address
  return `"${personne.name.replaceAll('"', '')}" <${personne.address}>`
}

function citer(texte) {
  return (texte || '')
    .replace(/\s+$/, '')
    .split('\n')
    .map((ligne) => `> ${ligne}`)
    .join('\n')
}

function prefixe(p, objet) {
  const propre = objet || ''
  return new RegExp(`^${p}\\s*:`, 'i').test(propre) ? propre : `${p}: ${propre}`
}

export const NOUVEAU = { mode: 'new', to: '', cc: '', subject: '', body: '' }

export function brouillon(mode, mail, adresseBoite) {
  const moi = (adresseBoite || '').toLowerCase()
  const estMoi = (p) => p.address.toLowerCase() === moi
  const expediteur = mail.replyTo?.[0] || mail.from?.[0]
  const deMoi = mail.from?.some(estMoi)
  const qui = expediteur ? champ(expediteur) : 'Quelqu’un'
  const entete = mail.date ? `Le ${dateComplete(mail.date)}, ${qui} a écrit :` : `${qui} a écrit :`
  if (mode === 'forward') {
    const lignes = [
      '',
      '',
      '---------- Message transféré ----------',
      `De : ${(mail.from || []).map(champ).join(', ')}`,
      `Date : ${dateComplete(mail.date)}`,
      `Objet : ${mail.subject || ''}`,
      `À : ${(mail.to || []).map(champ).join(', ')}`,
      ...(mail.cc?.length ? [`Cc : ${mail.cc.map(champ).join(', ')}`] : []),
      '',
      mail.text || '',
    ]
    return {
      mode,
      to: '',
      cc: '',
      subject: prefixe('Fwd', mail.subject),
      body: lignes.join('\n'),
      forward: { folder: mail.folder, uid: mail.uid },
      forwardAttachments: mail.attachments || [],
    }
  }
  // Répondre à un mail envoyé par le club : on écrit à ses destinataires.
  const principal = deMoi ? mail.to || [] : expediteur ? [expediteur] : []
  let cc = []
  if (mode === 'replyAll') {
    const vus = new Set(principal.map((p) => p.address.toLowerCase()))
    cc = [...(deMoi ? [] : mail.to || []), ...(mail.cc || [])].filter((p) => {
      const cle = p.address.toLowerCase()
      if (cle === moi || vus.has(cle)) return false
      vus.add(cle)
      return true
    })
  }
  return {
    mode,
    to: principal.map(champ).join(', '),
    cc: cc.map(champ).join(', '),
    subject: prefixe('Re', mail.subject),
    body: `\n\n${entete}\n${citer(mail.text)}`,
    inReplyTo: mail.messageId,
    references: mail.references,
    answered: { folder: mail.folder, uid: mail.uid },
  }
}
