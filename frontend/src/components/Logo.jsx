// Monogramme "Ct" (voir spec/SPEC.md 5.1 et images/login.png) : un grand
// anneau en "C" (ouvert en bas à droite) dans lequel vient s'emboîter un
// cercle plein contenant un "t" italique.
export default function Logo({ size = 40 }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
      <path
        d="M44 75.9A34 34 0 1 1 75.9 40"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="9"
        strokeLinecap="round"
      />
      <circle cx="67" cy="65" r="27" fill="var(--accent)" />
      <text
        x="67"
        y="76"
        textAnchor="middle"
        fontStyle="italic"
        fontFamily="Georgia, 'Times New Roman', serif"
        fontSize="30"
        fill="var(--bg)"
      >
        t
      </text>
    </svg>
  )
}
