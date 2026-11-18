// Puces de la boîte mail dans Messages, après « Chat » (spec/modules/mail.md
// §2, §4 bis ; Seb, 18 novembre) : une seule boîte (ou aucune), « Mail » ;
// plusieurs, une puce par boîte, à son nom, avec ses non lus.

const pastille = (n) => n > 0 && <span className="mail__pastille">{n}</span>

export function pucesMail(etat, total, parBoite) {
  const boites = etat.boxes ?? []
  if (boites.length < 2) {
    return [
      {
        value: 'mail',
        label: <>Mail{pastille(total)}</>,
      },
    ]
  }
  return boites.map((b) => ({
    value: b.id,
    label: (
      <>
        {b.name}
        {pastille(parBoite[b.id] ?? 0)}
      </>
    ),
  }))
}
