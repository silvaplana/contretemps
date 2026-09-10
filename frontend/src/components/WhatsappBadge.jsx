// Badge "groupe WhatsApp lié" (Admin > Conversations, voir spec/SPEC.md
// §6.9) — contrairement aux icônes de Icon.jsx (traits fins, monochromes),
// celui-ci reprend les couleurs de la vraie appli WhatsApp (rond vert,
// bulle blanche) pour rester immédiatement reconnaissable au milieu
// d'icônes plus neutres — un rond vert générique n'aurait pas suffi.
export default function WhatsappBadge({ size = 20 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <circle cx="12" cy="12" r="12" fill="#25D366" />
      {/* Bulle de discussion (silhouette simplifiée, pas le tracé de
          marque exact) : blanche sur le rond vert. */}
      <path
        fill="#fff"
        d="M12 5a7 7 0 0 0-5.8 10.85L5.3 19l3.27-.88A7 7 0 1 0 12 5Z"
      />
      {/* Combiné téléphonique en négatif (revient à la couleur du rond),
          incliné à 45°, façon logo WhatsApp — deux renflements + la
          barre qui les relie. */}
      <g fill="#25D366">
        <circle cx="9.3" cy="9.3" r="1.35" />
        <circle cx="14.7" cy="14.7" r="1.35" />
        <rect x="10.9" y="10.9" width="2.2" height="4.6" rx="1.1" transform="rotate(45 12 12)" />
      </g>
    </svg>
  )
}
