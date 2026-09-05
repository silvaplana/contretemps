// Petite bibliothèque d'icônes en ligne (traits fins, façon Tabler Icons —
// voir spec/SPEC.md section 7 "Charte visuelle"). Pas de dépendance externe :
// juste du SVG inline, un nom suffit à choisir le tracé.
const paths = {
  admin: 'M4 20c0-4 3.5-6 8-6s8 2 8 6 M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
  presence: 'M5 5h14v14H5z M9 3v4 M15 3v4 M5 10h14 M9 14l2 2 4-4',
  choregraphie: 'M9 18V5l11-2v13 M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3Z M20 16a3 3 0 1 1-3-3 3 3 0 0 1 3 3Z',
  video: 'M4 6h11v12H4z M15 10l5-3v10l-5-3',
  messagerie: 'M4 5h16v11H8l-4 4V5Z',
  profil: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M4 20c0-4 3.5-6 8-6s8 2 8 6',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z M16 16l5 5',
  plus: 'M12 5v14 M5 12h14',
  trash: 'M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13 M10 11v6 M14 11v6',
  chevronDown: 'M6 9l6 6 6-6',
  chevronRight: 'M9 6l6 6-6 6',
  chevronLeft: 'M15 6l-6 6 6 6',
  mail: 'M4 6h16v12H4z M4 7l8 6 8-6',
  check: 'M5 12l4 4 10-10',
  checkCheck: 'M2 12l4 4 8-8 M8 16l1 1 10-10',
  clock: 'M12 12V7 M12 12l4 2 M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z',
  x: 'M6 6l12 12 M18 6L6 18',
  play: 'M8 5l11 7-11 7V5Z',
  music: 'M9 18V5l11-2v13 M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3Z M20 16a3 3 0 1 1-3-3 3 3 0 0 1 3 3Z',
  users: 'M8 12a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z M17 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M2 20c0-3.5 3-5.5 6-5.5s6 2 6 5.5 M15 14.5c2.6.2 5 2 5 5.5',
  logout: 'M9 4H5v16h4 M13 8l4 4-4 4 M17 12H9',
  send: 'M4 12l16-8-6 16-3-6-7-2Z',
  edit: 'M4 20h4L18 10l-4-4L4 16v4Z',
  fileCheck: 'M6 3h9l3 3v15H6z M9 12l2 2 4-4',
  camera: 'M4 8h2l1.5-2h9L18 8h2a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z M12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
  folder: 'M4 6h6l2 2h8v11H4z',
}

// Icônes faites de points pleins plutôt que d'un tracé (menu "3 points").
const dotIcons = {
  moreVertical: [12, 5, 12, 12, 12, 19],
}

export default function Icon({ name, size = 20, className = '' }) {
  const dots = dotIcons[name]
  if (dots) {
    return (
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="currentColor"
        className={`icon ${className}`}
        aria-hidden="true"
      >
        {[0, 2, 4].map((i) => (
          <circle key={i} cx={dots[i]} cy={dots[i + 1]} r="1.8" />
        ))}
      </svg>
    )
  }

  const d = paths[name]
  if (!d) return null
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`icon ${className}`}
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  )
}
