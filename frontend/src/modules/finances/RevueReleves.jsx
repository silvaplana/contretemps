import { useState } from "react";

// Revue de l'import des relevés (financier.md §3.1, Seb 9/11) : rien n'est
// écrit avant Valider. Un tableau façon Excel, une ligne par relevé :
// Fichier | À quoi il correspond | Compte (modifiable dans sa case).
// Maquette : https://claude.ai/artifact/Cfxf9LG6GKEmYC19vd3dv2
export default function RevueReleves({ revue, onValider, onAnnuler }) {
  const [choix, setChoix] = useState(() => revue.rows.map((r) => r.account));
  const [enCours, setEnCours] = useState(false);
  const aChoisir = revue.rows.filter((r, i) => !r.error && choix[i] === null).length;

  function choisir(i, valeur) {
    const v = valeur === "" ? null : /^\d+$/.test(valeur) ? Number(valeur) : valeur;
    setChoix((c) => c.map((x, j) => (j === i ? v : x)));
  }

  async function valider() {
    setEnCours(true);
    try {
      await onValider(choix);
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="fin-revue" aria-label="Revue de l’import des relevés">
      <p>
        <strong>Voici ce que je propose.</strong> Rien n’est encore importé :
        vérifiez, changez le compte si besoin, puis validez.
      </p>
      <div className="fin-revue__tableau">
        <table>
          <thead>
            <tr>
              <th>Fichier</th>
              <th>À quoi il correspond</th>
              <th>Compte</th>
            </tr>
          </thead>
          <tbody>
            {revue.rows.map((r, i) => (
              <tr key={i} className={choix[i] === "skip" ? "fin-revue__ignore" : undefined}>
                <td>{r.file}</td>
                <td>
                  {r.error ? "Pas un relevé de banque" : r.what}
                  {r.already && <span className="fin-revue__tag">déjà importé</span>}
                  {r.error && <span className="fin-revue__tag fin-revue__tag--non">ignoré</span>}
                </td>
                <td className="fin-revue__compte">
                  {r.error ? (
                    "—"
                  ) : (
                    <select
                      value={choix[i] ?? ""}
                      className={choix[i] === null ? "fin-revue__a-choisir" : undefined}
                      aria-label={`Compte pour ${r.file}`}
                      onChange={(e) => choisir(i, e.target.value)}
                    >
                      <option value="">À choisir</option>
                      {revue.accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                      {r.newAccount && <option value="new">Nouveau : {r.newAccount}</option>}
                      <option value="skip">Ne pas importer</option>
                    </select>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        Chaque PDF va dans Docs › saison du relevé › Financier › RELEVES
        BANCAIRES › compte choisi. Un relevé déjà importé est seulement rangé.
      </p>
      {aChoisir > 0 && (
        <p className="fin-revue__aide">
          Choisissez le compte des relevés « À choisir » (ou « Ne pas importer »)
          pour pouvoir valider.
        </p>
      )}
      <div className="fin-revue__barre">
        <button type="button" className="btn btn--link" disabled={enCours} onClick={onAnnuler}>
          Annuler
        </button>
        <button type="button" className="btn btn--primary" disabled={aChoisir > 0 || enCours} onClick={valider}>
          {enCours ? "Import…" : "Valider"}
        </button>
      </div>
    </section>
  );
}
