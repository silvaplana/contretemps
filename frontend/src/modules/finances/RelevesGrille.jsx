import { useEffect, useState } from "react";
import { ouvrirDansDocs } from "../documents/lienDocs.js";
import * as api from "./api.js";

// Comptes ⋯ › « Relevés » (financier.md §3.2 bis, Seb 9/11) : par saison,
// une ligne par compte, une case par mois, pour voir les relevés importés
// et les trous. Maquette : https://claude.ai/artifact/5T8GbmNkh9UsnXKYC1krep

const REQUEST_EVENT = "finances-releves";

// Entrée « Relevés » du menu ⋯ (voir Financier.jsx).
export function requestStatements() {
  window.dispatchEvent(new Event(REQUEST_EVENT));
}
export const RELEVES_EVENT = REQUEST_EVENT;

const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const ETATS = {
  ok: { classe: "ok", texte: "✓", aide: "Relevé importé : toucher pour l’ouvrir" },
  quiet: { classe: "calme", texte: "–", aide: "Aucun mouvement : le relevé suivant repart du même solde" },
  missing: { classe: "manque", texte: "!", aide: "Il manque le relevé : les soldes ne se suivent pas" },
  bank: { classe: "banque", texte: "↓", aide: "Relevé à importer : la banque montre des opérations" },
  waiting: { classe: "attente", texte: "?", aide: "En attente du prochain relevé" },
  before: { classe: "vide", texte: "", aide: "Avant le premier relevé importé" },
  future: { classe: "vide", texte: "", aide: "Mois pas encore commencé" },
};

function libelle(month) {
  const [annee, mois] = month.split("-");
  return `${MOIS[Number(mois) - 1]} ${annee}`;
}

const aDesTrous = (saison) => saison.accounts.some((a) => a.months.some((m) => m.state === "missing"));

// `seasonId` : la saison à ouvrir (depuis Préparer, celle du bilan) ; sinon la saison en cours.
export default function RelevesGrille({ onClose, onImport, seasonId }) {
  const [saisons, setSaisons] = useState(null);
  const [choisie, setChoisie] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    api
      .grilleReleves()
      .then(({ seasons }) => {
        setSaisons(seasons);
        setChoisie((seasons.find((s) => s.id === seasonId) ?? seasons.find((s) => s.current) ?? seasons[0])?.id ?? null);
      })
      .catch((err) => setErreur(err.message));
  }, [seasonId]);

  const saison = saisons?.find((s) => s.id === choisie);
  const manquants = saison
    ? saison.accounts.flatMap((a) => a.months.filter((m) => m.state === "missing").map((m) => `${a.name} : ${libelle(m.month)}`))
    : [];

  function toucher(compte, m) {
    if (m.state === "ok" && m.docId) return ouvrirDansDocs(m.docId, { retour: true });
    if (m.state === "ok") return setMessage(`${compte.name}, ${libelle(m.month)} : ${m.file} (PDF pas encore rangé dans Docs : réimportez-le).`);
    setMessage(`${compte.name}, ${libelle(m.month)} : ${ETATS[m.state].aide}.`);
  }

  return (
    <div className="fin-releves">
      <button type="button" className="btn btn--link fin-releves__retour" onClick={onClose}>
        ← Comptes
      </button>
      <h3>Relevés</h3>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!saisons && !erreur && <p className="loading-label">Chargement…</p>}
      {saisons && (
        <>
          <div className="filter-chips" role="group" aria-label="Saison">
            {saisons.map((s) => (
              <button
                key={s.id}
                type="button"
                className={s.id === choisie ? "filter-chip filter-chip-active" : "filter-chip"}
                aria-pressed={s.id === choisie}
                onClick={() => {
                  setChoisie(s.id);
                  setMessage(null);
                }}
              >
                {s.name}
                {aDesTrous(s) && <i className="fin-releves__pastille" aria-label="relevés manquants" />}
              </button>
            ))}
          </div>
          {saison && saison.accounts.length === 0 && <p>Aucun compte pour l’instant : importez des relevés.</p>}
          {saison && saison.accounts.length > 0 && (
            <div className="fin-releves__grille">
              <table>
                <thead>
                  <tr>
                    <th className="fin-releves__compte">Compte</th>
                    {saison.accounts[0].months.map((m) => {
                      const [mois, annee] = libelle(m.month).split(" ");
                      return (
                        <th key={m.month}>
                          {mois}
                          <br />
                          {annee}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {saison.accounts.map((a) => (
                    <tr key={a.id}>
                      <td className="fin-releves__compte">{a.name}</td>
                      {a.months.map((m) => (
                        <td key={m.month}>
                          <button
                            type="button"
                            className={`fin-releves__case fin-releves__case--${ETATS[m.state].classe}`}
                            aria-label={`${a.name}, ${libelle(m.month)} : ${ETATS[m.state].aide}`}
                            onClick={() => toucher(a, m)}
                          >
                            {ETATS[m.state].texte}
                          </button>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {message && <p className="history-report">{message}</p>}
          <div className="fin-releves__legende">
            {["ok", "quiet", "missing", "bank", "waiting"].map((e) => (
              <span key={e}>
                <i className={`fin-releves__case fin-releves__case--${ETATS[e].classe}`}>{ETATS[e].texte}</i>
                {ETATS[e].aide}
              </span>
            ))}
          </div>
          {saison && (
            <p className={manquants.length ? "fin-releves__manquants" : "fin-releves__complet"}>
              {manquants.length ? (
                <>
                  <strong>
                    Il manque {manquants.length} relevé{manquants.length > 1 ? "s" : ""} en {saison.name} :
                  </strong>{" "}
                  {manquants.join(", ")}.
                </>
              ) : (
                <strong>Aucun relevé manquant en {saison.name}.</strong>
              )}
            </p>
          )}
          <button type="button" className="btn btn--primary" onClick={onImport}>
            Importer des relevés
          </button>
        </>
      )}
    </div>
  );
}
