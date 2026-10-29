// Sous-module Comptes (spec/modules/financier.md §3), repris de Sambo Admin
// (BankHistory.jsx) : etat des comptes de l'ecole, lus dans la base (voir
// backend/src/finances/) : total des comptes (vue par defaut) ou un compte
// seul, en graphique ou en tableau, categories, recherche, saisons. Import
// de releves PDF / archives depuis le menu ⋯ de Financier.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { normaliserRecherche } from "../../utils/recherche.js";
import * as api from "./api.js";
import { BalanceChart } from "./BalanceChart.jsx";
import BanquePanel from "./BanquePanel.jsx";
import FicheCompte from "./FicheCompte.jsx";
import Caisse from "./compta/Caisse.jsx";
import FicheOperation from "./compta/FicheOperation.jsx";
import PlanComptable, {
  PLAN_EVENTS,
  nomCompte,
} from "./compta/PlanComptable.jsx";
import SoldesDepart, { SOLDES_EVENTS } from "./compta/SoldesDepart.jsx";
import "./compta/compta.css";
import { CurveChart } from "./CurveChart.jsx";
import "./finances.css";

const DAY_MS = 24 * 3600 * 1000;
// Choix memorises sur cet appareil : comptes affiches, graphique ou tableau.
const VIEW_KEY = "finances-view";
const DISPLAY_KEY = "finances-display";
// Tableau : lignes affichees d'abord, puis par paquets en descendant.
const ROWS_PAGE = 50;
// Puce « Caisse » (spec §8.5) : le compte d'espèces, saisi à la main.
const CAISSE_VIEW = "caisse";
// Demande d'import de releves venue du menu ⋯ (voir requestStatementImport).
const IMPORT_EVENT = "finances-import";

// Entree "Importer des relevés" du menu ⋯ (voir Financier.jsx) : ouvre le
// choix de fichiers de Comptes.
export function requestStatementImport() {
  window.dispatchEvent(new Event(IMPORT_EVENT));
}

// Entree "Se connecter aux comptes en banque" du menu ⋯ : ouvre le volet de la banque.
const BANK_EVENT = "finances-banque";
export function requestBank() {
  window.dispatchEvent(new Event(BANK_EVENT));
}

// Retour de la banque (?banque=ok|annule|erreur, voir finances/bank.py) :
// lu une fois, puis retiré de l'adresse.
const RETOURS = {
  ok: "Banque connectée : choisissez les comptes suivis et leurs noms.",
  annule: "Connexion à la banque annulée.",
  erreur: "La connexion à la banque n’a pas abouti : recommencez.",
};
function lireRetourBanque() {
  try {
    const params = new URLSearchParams(window.location.search);
    const retour = params.get("banque");
    if (!retour) return null;
    params.delete("banque");
    const reste = params.toString();
    window.history.replaceState(
      null,
      "",
      window.location.pathname +
        (reste ? `?${reste}` : "") +
        window.location.hash,
    );
    return RETOURS[retour] ?? null;
  } catch {
    return null;
  }
}

function readSetting(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeSetting(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Stockage indisponible : le choix ne sera juste pas retenu.
  }
}

const { euros, dateFr } = api;

const plural = (n, word) => `${n} ${word}${n > 1 ? "s" : ""}`;

// Nom d'un compte dans les filtres et les colonnes du tableau : celui que
// lui a donné le trésorier (volet « Se connecter aux comptes en banque »), autant de comptes
// qu'il en faut (avant : « CC » et « Bleu », deux comptes seulement).
function shortName(account) {
  return account?.name ?? "";
}

function rowLabel(row) {
  return row.transfer
    ? `Virement ${row.transfer.from} → ${row.transfer.to}`
    : row.label;
}

// Serie du graphique (voir BalanceChart) : solde en fin de journee, un point
// par jour, du 1er au dernier jour connu. rows : lignes de l'historique (la
// plus recente en premier), value(row) : solde a suivre apres la ligne.
function ledgerSeries(rows, value) {
  const byDay = new Map();
  for (const row of [...rows].reverse()) {
    const v = value(row);
    if (v == null) continue;
    const t = Date.parse(`${row.date}T00:00:00Z`);
    const day = byDay.get(t) ?? { v, ops: [] };
    day.v = v;
    day.ops.push({ label: rowLabel(row), amount: row.amount });
    byDay.set(t, day);
  }
  if (byDay.size === 0) return [];
  const days = [...byDay.keys()];
  const last = Math.max(...days);
  const series = [];
  let v = null;
  for (let t = Math.min(...days); t <= last; t += DAY_MS) {
    const day = byDay.get(t);
    if (day) v = day.v;
    series.push({ t, v, ops: day?.ops ?? [] });
  }
  return series;
}

// Choix du menu "Categories" (voir BankHistory) : tout, les 5 operations
// les plus frequentes, les 5 plus grosses, ou une categorie precise (son
// nom). Les operations sont classees par le backend (finances/
// categories.py). Les "5 plus..." visent des operations, pas des
// categories (Seb, 28 octobre : sur un compte sans nos categories, tout
// tombait dans "Autres" et il ne restait que DECATHLON).
const ALL_CATEGORIES = "all";
const TOP_FREQUENT = "top-frequent";
const TOP_AMOUNT = "top-amount";
const TOP_COUNT = 5;

// Les 5 plus grosses operations (montant, recette ou depense), hors
// virements entre nos comptes.
function biggestRows(rows) {
  return [...rows]
    .filter((row) => !row.transfer)
    .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
    .slice(0, TOP_COUNT);
}

// Les operations des 5 libelles qui reviennent le plus souvent (abonnement,
// loyer...). Le libelle est compare sans ce qui change d'une fois a l'autre :
// les mots avec des chiffres (date, numero de carte) ; "CARTE 26/09/26
// DECATHLON 0010 CB*9481" -> "carte decathlon".
function labelKey(row) {
  return normaliserRecherche(row.label)
    .split(/\s+/)
    .filter((word) => word && !/\d/.test(word))
    .join(" ");
}

function mostFrequentRows(rows) {
  const counts = new Map();
  for (const row of rows) {
    if (row.transfer) continue;
    const key = labelKey(row);
    if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const keys = new Set(
    [...counts.entries()]
      // Une operation unique n'est pas "frequente".
      .filter(([, count]) => count > 1)
      .sort((a, b) => b[1] - a[1])
      .slice(0, TOP_COUNT)
      .map(([key]) => key),
  );
  return rows.filter((row) => !row.transfer && keys.has(labelKey(row)));
}

// Par categorie : nombre d'operations, recettes, depenses et total. Un
// virement interne ne compte pas (ni recette ni depense).
function categoryStats(rows) {
  const stats = new Map();
  for (const row of rows) {
    const stat = stats.get(row.category) ?? {
      name: row.category,
      count: 0,
      income: 0,
      expense: 0,
      total: 0,
    };
    stat.count += 1;
    if (!row.transfer) {
      if (row.amount > 0) stat.income += row.amount;
      else stat.expense += row.amount;
      stat.total += row.amount;
    }
    stats.set(row.category, stat);
  }
  return stats;
}

// Serie du graphique quand un filtre est actif : cumul des operations
// retenues (ex: ce que les salaires ont coute depuis le debut), un point
// par jour entre la 1re et la derniere.
function cumulativeSeries(rows) {
  let sum = 0;
  const cumulated = [...rows].reverse().map((row) => {
    sum += row.transfer ? 0 : row.amount;
    return { ...row, cumul: Math.round(sum * 100) / 100 };
  });
  const series = ledgerSeries(cumulated.reverse(), (row) => row.cumul);
  // Depart a 0 la veille de la 1re operation : la variation affichee sur
  // toute la periode est ainsi le total des operations retenues.
  if (series.length > 0)
    series.unshift({ t: series[0].t - DAY_MS, v: 0, ops: [] });
  return series;
}

// Periode "Saisons" du graphique : la courbe affichee (comptes et categories
// choisis) decoupee par saison, les saisons superposees sur le meme axe du
// 1er juillet au 30 juin. Sous le graphique, un clic sur une saison de la
// legende la masque ou la reaffiche, comme dans l'onglet Saisons.
// Cumul des operations retenues, remis a zero au debut de chaque saison (une
// valeur par jour d'operation). Un ensemble de depenses (total negatif) est
// compte en positif, pour que la courbe monte avec ce qui est depense.
function seasonalCumul(rows, seasons) {
  const amount = (row) => (row.transfer ? 0 : row.amount);
  const spending = rows.reduce((sum, row) => sum + amount(row), 0) < 0;
  const oldestFirst = [...rows].sort((a, b) => a.date.localeCompare(b.date));
  const byDate = new Map();
  for (const season of seasons) {
    let sum = 0;
    byDate.set(season.startDate, 0);
    for (const row of oldestFirst) {
      if (row.date < season.startDate || row.date > season.endDate) continue;
      sum += spending ? -amount(row) : amount(row);
      byDate.set(row.date, Math.round(sum * 100) / 100);
    }
  }
  const series = [...byDate]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, total]) => ({ date, total }));
  return { series, spending };
}

function SeasonsOverlay({ series, rows, filtering, seasonsData }) {
  if (!seasonsData)
    return <p className="balance-chart-empty">Chargement des saisons…</p>;
  const seasons = seasonsData.seasons;
  if (seasons.length === 0)
    return (
      <p className="balance-chart-empty">
        Aucune saison : créez-la d’abord dans Admin › École.
      </p>
    );
  // Sans filtre : le solde. Avec un filtre : le cumul des operations
  // retenues depuis le debut de chaque saison (pas depuis le 1er releve).
  const cumul = filtering ? seasonalCumul(rows, seasons) : null;
  const data = {
    seasons,
    today: seasonsData.today,
    series: cumul
      ? cumul.series
      : series
          .filter((p) => p.v != null)
          .map((p) => ({
            date: new Date(p.t).toISOString().slice(0, 10),
            total: p.v,
          })),
  };
  const current = seasons.find((s) => s.current) ?? seasons[seasons.length - 1];
  return (
    <>
      {cumul && (
        <p className="history-chart-note">
          {cumul.spending ? "Dépenses cumulées" : "Recettes cumulées"} depuis le
          début de chaque saison
        </p>
      )}
      <CurveChart
        data={data}
        selected={current}
        mode="overlay"
        hiddenKey="finances-seasons-hidden"
      />
    </>
  );
}

export default function Comptes() {
  const [view, setView] = useState(() => readSetting(VIEW_KEY, "all"));
  const [display, setDisplay] = useState(() =>
    readSetting(DISPLAY_KEY, "chart"),
  );
  const [ledger, setLedger] = useState(null);
  const [error, setError] = useState(null);
  const [importing, setImporting] = useState(false);
  // Compte rendu du dernier import : une phrase, puis les releves refuses.
  const [importReport, setImportReport] = useState(null);
  const [importErrors, setImportErrors] = useState([]);
  const [shownRows, setShownRows] = useState(ROWS_PAGE);
  // Filtres sur la nature des operations : menu "Categories" + recherche.
  const [category, setCategory] = useState(ALL_CATEGORIES);
  const [search, setSearch] = useState("");
  // Saisons de l’ecole (periode "Saisons" du graphique, voir SeasonsOverlay).
  const [seasonsData, setSeasonsData] = useState(null);
  const fileInput = useRef(null);
  const sentinel = useRef(null);
  // Volet « Se connecter aux comptes en banque », et message du retour de la banque.
  const [retourBanque] = useState(lireRetourBanque);
  const [banqueOuverte, setBanqueOuverte] = useState(
    () => retourBanque === RETOURS.ok,
  );
  // Compte dont la fiche est ouverte (« Voir le compte »), par son id.
  const [fiche, setFiche] = useState(null);
  // Fiche d'une opération (appui sur une ligne, spec §8.4), volet
  // ⋯ › Plan comptable (§8.2), puces Sans compte / Sans pièce.
  const [ficheOp, setFicheOp] = useState(null);
  const [volet, setVolet] = useState(null); // null | 'plan' | 'soldes'
  const [manque, setManque] = useState(null); // null | 'account' | 'piece'

  const load = useCallback(async () => {
    try {
      setLedger(
        await api.historique(
          view === "all" || view === CAISSE_VIEW ? null : view,
        ),
      );
      setError(null);
    } catch (err) {
      // Compte memorise qui n'existe plus : retour a la vue d'ensemble.
      if (view !== "all") setView("all");
      else setError(err.message);
    }
  }, [view]);

  useEffect(() => {
    load();
  }, [load]);

  // Saisons de l'ecole, pour la periode "Saisons" du graphique.
  useEffect(() => {
    api
      .saisons()
      .then(setSeasonsData)
      .catch(() => {
        // Saisons indisponibles : les autres periodes restent utilisables.
      });
  }, []);

  // Menu ⋯ > "Se connecter aux comptes en banque".
  useEffect(() => {
    const open = () => setBanqueOuverte(true);
    window.addEventListener(BANK_EVENT, open);
    return () => window.removeEventListener(BANK_EVENT, open);
  }, []);

  // Menu ⋯ > « Plan comptable » et « Soldes de départ ».
  useEffect(() => {
    const plan = () => setVolet("plan");
    const soldes = () => setVolet("soldes");
    window.addEventListener(PLAN_EVENTS.plan, plan);
    window.addEventListener(SOLDES_EVENTS.soldes, soldes);
    return () => {
      window.removeEventListener(PLAN_EVENTS.plan, plan);
      window.removeEventListener(SOLDES_EVENTS.soldes, soldes);
    };
  }, []);

  // Menu ⋯ > "Importer des relevés".
  useEffect(() => {
    const open = () => fileInput.current?.click();
    window.addEventListener(IMPORT_EVENT, open);
    return () => window.removeEventListener(IMPORT_EVENT, open);
  }, []);

  async function importFiles(event) {
    const files = [...event.target.files];
    event.target.value = "";
    if (files.length === 0) return;
    setImporting(true);
    setImportReport(null);
    setImportErrors([]);
    try {
      const report = await api.importerReleves(files);
      const operations = report.imported.reduce(
        (n, i) => n + Number.parseInt(i.detail.split(", ")[1]),
        0,
      );
      const parts = [
        `${plural(report.imported.length, "relevé")} importé${report.imported.length > 1 ? "s" : ""}`,
      ];
      if (report.imported.length)
        parts[0] += ` (${plural(operations, "opération")})`;
      if (report.skipped.length)
        parts.push(
          `${report.skipped.length} déjà présent${report.skipped.length > 1 ? "s" : ""}`,
        );
      if (report.errors.length)
        parts.push(
          `${report.errors.length} refusé${report.errors.length > 1 ? "s" : ""}`,
        );
      setImportReport(parts.join(", "));
      setImportErrors(report.errors);
      await load();
    } catch (err) {
      setImportReport(`Import impossible : ${err.message}`);
    } finally {
      setImporting(false);
    }
  }

  function chooseView(next) {
    setView(next);
    setShownRows(ROWS_PAGE);
    writeSetting(VIEW_KEY, next);
  }

  function chooseDisplay(next) {
    setDisplay(next);
    setShownRows(ROWS_PAGE);
    writeSetting(DISPLAY_KEY, next);
  }

  function chooseCategory(next) {
    setCategory(next);
    setShownRows(ROWS_PAGE);
  }

  function chooseSearch(next) {
    setSearch(next);
    setShownRows(ROWS_PAGE);
  }

  const caisse = view === CAISSE_VIEW;
  const single = view !== "all" && !caisse;

  // Categories presentes, et operations retenues par le menu (null :
  // toutes).
  const stats = useMemo(() => categoryStats(ledger?.rows ?? []), [ledger]);
  const selectedRows = useMemo(() => {
    if (!ledger || category === ALL_CATEGORIES) return null;
    if (category === TOP_AMOUNT) return new Set(biggestRows(ledger.rows));
    if (category === TOP_FREQUENT)
      return new Set(mostFrequentRows(ledger.rows));
    return new Set(ledger.rows.filter((row) => row.category === category));
  }, [category, ledger]);

  // Operations retenues par le menu et la recherche (libelle, details ou
  // categorie, sans tenir compte des majuscules ni des accents).
  const wanted = normaliserRecherche(search.trim());
  const filtering = selectedRows !== null || wanted !== "" || manque !== null;
  const rows = useMemo(() => {
    if (!ledger) return [];
    if (!filtering) return ledger.rows;
    return ledger.rows.filter(
      (row) =>
        (selectedRows === null || selectedRows.has(row)) &&
        (manque === null || (!row.transfer && row[manque] == null)) &&
        (wanted === "" ||
          normaliserRecherche(
            `${rowLabel(row)} ${row.details} ${row.category}`,
          ).includes(wanted)),
    );
  }, [ledger, filtering, selectedRows, wanted, manque]);
  // Recettes, depenses et detail par categorie de la selection.
  const selection = useMemo(() => {
    const perCategory = [...categoryStats(rows).values()].sort(
      (a, b) => Math.abs(b.total) - Math.abs(a.total),
    );
    return {
      perCategory,
      income: perCategory.reduce((sum, stat) => sum + stat.income, 0),
      expense: perCategory.reduce((sum, stat) => sum + stat.expense, 0),
    };
  }, [rows]);

  // Graphique : solde des comptes, ou cumul des operations retenues quand un
  // filtre est actif (le solde n'aurait plus de sens).
  const series = useMemo(() => {
    if (!ledger) return [];
    if (filtering) return cumulativeSeries(rows);
    return ledgerSeries(
      ledger.rows,
      single ? (row) => row.balances[view] : (row) => row.total,
    );
  }, [ledger, filtering, rows, single, view]);

  // Tableau : n'affiche que les premieres lignes, puis la suite quand on
  // arrive en bas de la zone qui defile.
  const rowCount = rows.length;
  useEffect(() => {
    if (display !== "table" || !sentinel.current) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting)
        setShownRows((n) => Math.min(n + ROWS_PAGE, rowCount));
    });
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [display, rowCount, shownRows]);

  const input = (
    <input
      ref={fileInput}
      type="file"
      accept=".pdf,.zip,.7z,.tar,.gz,.tgz,.bz2,.xz,application/pdf,application/zip"
      multiple
      hidden
      onChange={importFiles}
    />
  );

  if (error) return <p className="login-screen__erreur">{error}</p>;
  const banque = (
    <>
      {retourBanque && <p className="history-report">{retourBanque}</p>}
      {banqueOuverte && (
        <BanquePanel
          accounts={ledger?.allAccounts ?? []}
          onChanged={load}
          onClose={() => setBanqueOuverte(false)}
        />
      )}
    </>
  );

  // Volet de la banque ouvert : lui seul, sans le total ni l'historique
  // (Seb, 28 octobre).
  if (!ledger || banqueOuverte) {
    return (
      <>
        {banque}
        {input}
      </>
    );
  }
  if (volet === "soldes") {
    return <SoldesDepart onClose={() => setVolet(null)} />;
  }
  if (volet) {
    return (
      <PlanComptable
        onClose={() => {
          setVolet(null);
          load();
        }}
      />
    );
  }

  const allAccounts = ledger.allAccounts;
  const accounts = single ? ledger.accounts : allAccounts;
  const shown = ledger.accounts;
  const filters = [
    { id: "all", label: "Tous" },
    ...allAccounts.map((a) => ({ id: String(a.id), label: shortName(a) })),
    { id: CAISSE_VIEW, label: "Caisse" },
  ];

  return (
    <div className="fin-comptes account-card">
      {banque}
      {input}
      {ficheOp && (
        <FicheOperation
          operationId={ficheOp}
          onClose={() => setFicheOp(null)}
          onChange={load}
        />
      )}
      <div className="account-card-header">
        <div>
          <h3>
            {caisse ? "Caisse" : single ? shown[0]?.name : "Total des comptes"}
          </h3>
          <span className="account-iban">
            {single
              ? shown[0]?.asOf && `au ${dateFr(shown[0].asOf)}`
              : shown
                  .map(
                    (a) =>
                      `${a.name} ${a.balance == null ? "—" : euros(a.balance)}`,
                  )
                  .join(" · ")}
            {single && shown[0] && fiche !== shown[0].id && (
              <>
                {shown[0].asOf && " · "}
                <button
                  type="button"
                  className="btn btn--link"
                  onClick={() => setFiche(shown[0].id)}
                >
                  Voir le compte
                </button>
              </>
            )}
          </span>
        </div>
        <span className="account-balance">{euros(ledger.total)}</span>
      </div>
      {single && shown[0] && fiche === shown[0].id && (
        <FicheCompte
          compte={shown[0]}
          onChanged={load}
          onClose={() => setFiche(null)}
        />
      )}

      {importing && <p className="loading-label">Import des relevés…</p>}
      {importReport && <p className="history-report">{importReport}</p>}
      {importErrors.map((e) => (
        <p key={e.file} className="login-screen__erreur">
          {e.file} : {e.detail}
        </p>
      ))}

      {/* Seulement quand AUCUN compte n'a d'opération : un compte vide
          choisi (ex. un livret qui ne bouge pas) garde les puces, sinon on
          ne pouvait plus revenir à « Tous » (Seb, 28 octobre). */}
      {ledger.rows.length === 0 && !single ? (
        <p>
          Aucune opération pour l’instant : menu ⋯ en haut à droite › Se
          connecter aux comptes en banque, ou Importer des relevés (PDF ou
          archive).
        </p>
      ) : (
        <>
          <div className="history-toolbar">
            {filters.length > 2 && (
              <div
                className="filter-chips"
                role="group"
                aria-label="Comptes affichés"
              >
                {filters.map((f) => (
                  <button
                    key={f.id}
                    className={
                      f.id === view
                        ? "filter-chip filter-chip-active"
                        : "filter-chip"
                    }
                    aria-pressed={f.id === view}
                    onClick={() => chooseView(f.id)}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            )}
            {ledger.counts && !caisse && (
              <div
                className="filter-chips"
                role="group"
                aria-label="À compléter"
              >
                {[
                  {
                    id: "account",
                    label: "Sans compte",
                    n: ledger.counts.withoutAccount,
                  },
                  {
                    id: "piece",
                    label: "Sans pièce",
                    n: ledger.counts.withoutPiece,
                  },
                ].map((m) => (
                  <button
                    key={m.id}
                    className={
                      m.id === manque
                        ? "filter-chip filter-chip-active"
                        : "filter-chip"
                    }
                    aria-pressed={m.id === manque}
                    onClick={() => {
                      setManque((v) => (v === m.id ? null : m.id));
                      setShownRows(ROWS_PAGE);
                      if (display !== "table") chooseDisplay("table");
                    }}
                  >
                    {m.label} ({m.n})
                  </button>
                ))}
              </div>
            )}
            <div className="filter-chips" role="group" aria-label="Affichage">
              {[
                { id: "chart", label: "Graphique" },
                { id: "table", label: "Tableau" },
              ].map((d) => (
                <button
                  key={d.id}
                  className={
                    d.id === display
                      ? "filter-chip filter-chip-active"
                      : "filter-chip"
                  }
                  aria-pressed={d.id === display}
                  onClick={() => chooseDisplay(d.id)}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {!caisse && (
            <div className="history-filters">
              <select
                value={category}
                onChange={(e) => chooseCategory(e.target.value)}
                aria-label="Catégories affichées"
                className={
                  category === ALL_CATEGORIES
                    ? undefined
                    : "history-filter-active"
                }
              >
                <option value={ALL_CATEGORIES}>Toutes les catégories</option>
                <option value={TOP_AMOUNT}>
                  Les {TOP_COUNT} plus grosses opérations
                </option>
                <option value={TOP_FREQUENT}>
                  Les {TOP_COUNT} opérations les plus fréquentes
                </option>
                <optgroup label="Une catégorie">
                  {ledger.categories
                    .filter((name) => stats.has(name))
                    .map((name) => (
                      <option key={name} value={name}>
                        {name} ({stats.get(name).count})
                      </option>
                    ))}
                </optgroup>
              </select>
              <label className="member-search">
                <span aria-hidden="true">🔍</span>
                <input
                  type="search"
                  name="operation-search"
                  placeholder="Rechercher une opération..."
                  value={search}
                  onChange={(e) => chooseSearch(e.target.value)}
                />
              </label>
            </div>
          )}

          {filtering && (
            <div className="history-selection">
              <p>
                <strong>{plural(rows.length, "opération")}</strong> · Recettes{" "}
                <span className="success-state">
                  +{euros(selection.income)}
                </span>{" "}
                · Dépenses{" "}
                <span className="unpaid-amount">
                  {euros(selection.expense)}
                </span>{" "}
                · Net{" "}
                <strong>{euros(selection.income + selection.expense)}</strong>
              </p>
              {selection.perCategory.length > 1 && (
                <ul>
                  {selection.perCategory.map((stat) => (
                    <li key={stat.name}>
                      <button
                        className="history-category"
                        onClick={() => chooseCategory(stat.name)}
                      >
                        {stat.name}
                      </button>{" "}
                      <span
                        className={
                          stat.total < 0 ? "unpaid-amount" : "success-state"
                        }
                      >
                        {stat.total > 0 ? "+" : ""}
                        {euros(stat.total)}
                      </span>{" "}
                      <small>({plural(stat.count, "opération")})</small>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {caisse ? (
            <Caisse
              retraits={ledger.rows.filter(
                (r) =>
                  !r.transfer &&
                  r.amount < 0 &&
                  /RETRAIT|DAB|DISTRIB/i.test(r.label),
              )}
            />
          ) : rows.length === 0 ? (
            <p className="empty-state">Aucune opération ne correspond</p>
          ) : display === "chart" ? (
            <>
              {filtering && (
                <p className="history-chart-note">
                  Cumul des opérations retenues, depuis le début de la période
                </p>
              )}
              <BalanceChart
                series={series}
                showPercent={!filtering}
                fromZero={filtering}
                extraRange={{
                  label: "Saisons",
                  content: (
                    <SeasonsOverlay
                      series={series}
                      rows={rows}
                      filtering={filtering}
                      seasonsData={seasonsData}
                    />
                  ),
                }}
              />
            </>
          ) : (
            <div className="table-wrapper operations-scroll history-table">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Libellé</th>
                    <th className="amount-cell">Montant</th>
                    {!single &&
                      accounts.map((a) => (
                        <th key={a.id} className="amount-cell">
                          {shortName(a)}
                        </th>
                      ))}
                    <th className="amount-cell">
                      {single ? "Solde" : "Total"}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, shownRows).map((row) => {
                    const name = shortName(
                      accounts.find((a) => a.id === row.accountId),
                    );
                    const subline = [
                      !row.transfer && row.category,
                      !single && !row.transfer && name,
                      row.provisional && "banque, en attente du relevé",
                      row.details.split("\n")[0],
                    ];
                    return (
                      <tr
                        key={row.id}
                        className={
                          row.transfer ? "history-transfer" : "fin-cp-cliquable"
                        }
                        onClick={
                          row.transfer ? undefined : () => setFicheOp(row.id)
                        }
                      >
                        <td>{dateFr(row.date)}</td>
                        <td title={row.details || undefined}>
                          {rowLabel(row)}
                          <span className="history-details">
                            {subline.filter(Boolean).join(" · ")}
                          </span>
                          {/* Compte du plan confirmé, proposé (à confirmer) ou à choisir, et pièce (spec §8.4). */}
                          {!row.transfer && (
                            <span className="fin-cp-sous">
                              {row.account
                                ? nomCompte(row.account) +
                                  (row.account.split ? " (ventilé)" : "")
                                : row.proposal
                                  ? `${nomCompte(row.proposal)} ?`
                                  : "Compte à choisir"}
                              {row.piece ? (
                                <span className="badge badge--success">
                                  {row.piece.kind}
                                </span>
                              ) : (
                                <span className="badge badge--warning">
                                  sans pièce
                                </span>
                              )}
                            </span>
                          )}
                        </td>
                        <td
                          className={`amount-cell ${row.transfer ? "" : row.amount < 0 ? "unpaid-amount" : "success-state"}`}
                        >
                          {row.transfer ? "⇄ " : row.amount > 0 ? "+" : ""}
                          {euros(row.amount)}
                        </td>
                        {!single &&
                          accounts.map((a) => (
                            <td
                              key={a.id}
                              className="amount-cell history-balance"
                            >
                              {row.balances[a.id] == null
                                ? "—"
                                : euros(row.balances[a.id])}
                            </td>
                          ))}
                        <td className="amount-cell history-total">
                          {/* Solde absent : opérations de l'ancien compte, le temps que
                              celles du compte choisi arrivent (page vide avant). */}
                          {single
                            ? row.balances[view] == null
                              ? "—"
                              : euros(row.balances[view])
                            : row.total == null
                              ? "—"
                              : euros(row.total)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {shownRows < rows.length && (
                <div ref={sentinel} className="history-more" />
              )}
            </div>
          )}
        </>
      )}

      {(shown.some((a) => a.coverage.length) || ledger.issues.length > 0) && (
        <div className="history-statements">
          {shown.map((a) => (
            <p key={a.id}>
              Relevés {a.name} :{" "}
              {a.coverage
                .map(
                  (c) =>
                    `du ${dateFr(c.from)} au ${dateFr(c.to)} (${plural(c.statements, "relevé")})`,
                )
                .join(", puis ")}
            </p>
          ))}
          {ledger.issues.map((issue) => (
            <p key={issue} className="login-screen__erreur">
              {issue}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
