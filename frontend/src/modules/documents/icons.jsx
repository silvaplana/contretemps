// Dessins de l'explorateur (spec documents.md §7.1, §7.1 bis, §7.1 ter) :
// dossier jaune, page à coin plié avec l'étiquette du type, badges de
// statut, pastilles des familles Informer / Questionner / Agir.

import { FAMILIES, STATUSES, fileType } from './kinds.js'

export function StatusIcon({ status }) {
  if (status === 'draft') {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 20h4L19 9l-4-4L4 16z" />
        <path d="M13.5 6.5l4 4" />
      </svg>
    )
  }
  if (status === 'validated') {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M5 12.5l4.5 4.5L19 7.5" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2.5l2.4 1.8 3-.2.9 2.9 2.4 1.8-1 2.8 1 2.8-2.4 1.8-.9 2.9-3-.2L12 21.5l-2.4-1.8-3 .2-.9-2.9-2.4-1.8 1-2.8-1-2.8 2.4-1.8.9-2.9 3 .2z" />
      <path d="M8.5 12l2.5 2.5 4.5-5" />
    </svg>
  )
}

export function StatusBadge({ status }) {
  const s = STATUSES[status]
  if (!s) return null
  return (
    <span className={`dx-badge dx-badge--${s.className}`}>
      <StatusIcon status={status} />
      {s.label}
    </span>
  )
}

export function FamilyDot({ family, size = 20 }) {
  const f = FAMILIES[family]
  return (
    <span
      className={`dx-famdot${family === 'inform' ? ' dx-famdot--i' : ''}`}
      style={{ background: f.color, width: size, height: size, fontSize: size * 0.6 }}
      aria-hidden="true"
    >
      {f.glyph}
    </span>
  )
}

export function FolderIcon({ restricted = false }) {
  return (
    <span className="dx-folder" aria-hidden="true">
      <svg viewBox="0 0 56 46">
        <path d="M4 8a4 4 0 0 1 4-4h13l5 6h22a4 4 0 0 1 4 4v24a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" fill="var(--dx-folder-back)" />
        <path d="M4 16a4 4 0 0 1 4-4h40a4 4 0 0 1 4 4v22a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" fill="var(--dx-folder)" />
      </svg>
      {restricted && <span className="dx-folder__lock">🔒</span>}
    </span>
  )
}

// Page à coin plié : étiquette du type pour un fichier importé, pastille de
// famille pour un fichier de l'appli, rien pour un fichier vierge.
export function FileIcon({ name, family, blank = false }) {
  const type = fileType(name)
  return (
    <svg className="dx-page" viewBox="0 0 44 54" aria-hidden="true">
      <path d="M4 4a3 3 0 0 1 3-3h22l12 12v37a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z" fill="var(--dx-page)" stroke="var(--dx-page-line)" strokeWidth="1.5" />
      <path d="M29 1v9a3 3 0 0 0 3 3h9" fill="var(--dx-page-fold)" stroke="var(--dx-page-line)" strokeWidth="1.5" />
      {family && FAMILIES[family] ? (
        <>
          <circle cx="21" cy="36" r="12" fill={FAMILIES[family].color} />
          <circle cx="21" cy="36" r="9" fill="none" stroke="#fff" strokeWidth="1.6" />
          {family === 'act' ? (
            <path d="M22.5 29.5 L17.5 37 H21 L19.5 42.5 L24.5 35 H21 Z" fill="#fff" />
          ) : (
            <text
              x="21" y="40.5" textAnchor="middle" fontSize="12" fontWeight="700" fill="#fff"
              fontStyle={family === 'inform' ? 'italic' : 'normal'}
              fontFamily={family === 'inform' ? 'Georgia, serif' : 'system-ui, sans-serif'}
            >
              {FAMILIES[family].glyph}
            </text>
          )}
        </>
      ) : (
        !blank &&
        type.label && (
          <>
            <rect x="4" y="30" width="30" height="16" rx="3" fill={type.color} />
            <text x="19" y="42" textAnchor="middle" fontSize={type.label.length > 2 ? 9.5 : 12} fontWeight="700" fill="#fff" fontFamily="system-ui, sans-serif">
              {type.label}
            </text>
          </>
        )
      )}
    </svg>
  )
}

export function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

export function BubbleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 18V7a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H8z" />
      <path d="M9 9.5h6M9 12.5h4" />
    </svg>
  )
}
