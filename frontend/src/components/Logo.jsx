// Logo Contretemps : image fournie par l'utilisateur (public/images/
// logo-contretemps.jpg — même image que le favicon/l'icône Android, voir
// index.html et android/app/src/main/res/mipmap-*). Affichée grande sur
// Login, petite dans les en-têtes.
//
// L'ancien monogramme "Ct" (arc clair + cercle orange + "t" italique) reste
// en dessous, gardé intact, au cas où on voudrait un jour s'en ressortir
// sans avoir à le réécrire — passer AFFICHER_LOGO_PHOTO à `false` pour y
// revenir.
const AFFICHER_LOGO_PHOTO = true
const BASE_URL = import.meta.env.BASE_URL

export default function Logo({ size = 40 }) {
  if (AFFICHER_LOGO_PHOTO) {
    return (
      <img
        src={`${BASE_URL}images/logo-contretemps.jpg`}
        width={size}
        height={size}
        alt="Logo Contretemps"
        style={{ borderRadius: 8, objectFit: 'cover' }}
      />
    )
  }

  return (
    <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
      <path
        d="M78 22a34 34 0 1 0 8 21"
        fill="none"
        stroke="var(--card-bg)"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="58" cy="55" r="30" fill="var(--accent)" />
      <text
        x="58"
        y="68"
        textAnchor="middle"
        fontStyle="italic"
        fontFamily="Georgia, 'Times New Roman', serif"
        fontSize="34"
        fill="var(--card-bg)"
      >
        t
      </text>
    </svg>
  )
}
