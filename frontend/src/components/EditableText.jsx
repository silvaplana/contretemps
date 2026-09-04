// Champ texte "toujours éditable" utilisé dans les tableaux Admin : visuellement
// discret (pas de bordure) tant qu'il n'a pas le focus, pour rester lisible en
// mode consultation tout en restant éditable au clic (voir spec/SPEC.md 5.1.1).
export default function EditableText({ value, onChange, type = 'text', placeholder }) {
  return (
    <input
      className="editable-text"
      type={type}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}
