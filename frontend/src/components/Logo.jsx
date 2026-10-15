import { urlLogo, useApparence } from '../api/apparence.js'

// Logo Contretemps : image fournie par l'utilisateur (public/images/
// logo-contretemps.png — même image que le favicon/l'icône Android, voir
// index.html et android/app/src/main/res/mipmap-*). Affichée grande sur
// Login, petite dans les en-têtes.
//
// PNG (pas jpg) : le fichier source est détouré, fond transparent autour du
// cadran — un jpg aurait forcé un fond opaque et perdu ce détourage. Pas de
// borderRadius/objectFit ici pour la même raison : il n'y a pas de coins
// carrés à arrondir, le détourage s'en occupe déjà.
//
// L'ancien monogramme "Ct" (arc clair + cercle orange + "t" italique) reste
// en dessous, gardé intact, au cas où on voudrait un jour s'en ressortir
// sans avoir à le réécrire — passer AFFICHER_LOGO_PHOTO à `false` pour y
// revenir.
//
// Depuis le 2026-10-15, une école peut avoir son propre logo (Admin > École
// > Personnalisation de l'application, voir api/apparence.js).
const AFFICHER_LOGO_PHOTO = true

export default function Logo({ size = 40 }) {
  const apparence = useApparence()
  if (AFFICHER_LOGO_PHOTO) {
    return (
      <img
        src={urlLogo(apparence)}
        width={size}
        height={size}
        style={{ objectFit: 'contain' }}
        alt={`Logo ${apparence.nom}`}
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
