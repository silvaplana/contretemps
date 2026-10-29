// Données d'EXEMPLE des écrans « Pièces et comptabilité » (spec/modules/
// financier.md §8), montrés à la trésorière avant de coder l'étape 1. Rien
// n'est enregistré sur le serveur : les chiffres sont ceux de 2024-25
// (Balance et Grand livre de la comptable), les écrans vivent en mémoire.
// À supprimer quand l'étape 1 (tables fin_chart_accounts, fin_documents…)
// les remplace.

const NIVEAU_KEY = 'finances-niveau-exemple'

export function lireNiveau() {
  try {
    return localStorage.getItem(NIVEAU_KEY) === 'simple' ? 'simple' : 'complet'
  } catch {
    return 'complet'
  }
}

export function ecrireNiveau(niveau) {
  try {
    localStorage.setItem(NIVEAU_KEY, niveau)
  } catch {
    // Pas retenu, tant pis.
  }
}

export const eur = (n) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(n)

export const dateFr = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR')

// Plan comptable de l'école, repris de la Balance 2024-25. `mots` : ce qui,
// dans un libellé de banque, fait proposer ce compte.
export const PLAN = [
  { num: '6063', label: 'Autres fournitures', nature: 'depense', mots: ['AMAZON', 'TEMU', 'ALI EXPRESS', 'CASTORAMA', 'IKEA', 'DARTY'], nb: 14 },
  { num: '6064', label: 'Fournitures administratives', nature: 'depense', mots: ['BUREAU VALLEE', 'ONLINEPRINTERS'], nb: 3 },
  { num: '607', label: 'Tissus, mercerie, accessoires', nature: 'depense', mots: ['MELLE DANSE', 'MADEMOISELLE DANSE', 'KIABI'], nb: 9 },
  { num: '613', label: 'Location Galli', nature: 'depense', evenement: 'gala', mots: ['GALLI'], nb: 1 },
  { num: '6135', label: 'Hébergement du site', nature: 'depense', mots: ['OVH', 'IONOS'], nb: 1 },
  { num: '615', label: 'Entretien et réparations', nature: 'depense', mots: [], nb: 1 },
  { num: '616', label: 'Assurance MAIF', nature: 'depense', mots: ['MAIF'], nb: 1 },
  { num: '622', label: 'Intervenants (technicien, sécurité)', nature: 'depense', evenement: 'gala', mots: ['POMPIER', 'TECHNICIEN'], nb: 2 },
  { num: '6226', label: 'Honoraires des professeurs', nature: 'depense', mots: ['REVELLES', 'DE LUCA', 'PESENTI', 'THOMAS'], nb: 62 },
  { num: '6228', label: 'Travaux de couture', nature: 'depense', evenement: 'gala', mots: ['COUTURE'], nb: 2 },
  { num: '623', label: 'Publicité', nature: 'depense', mots: ['FLYERS', 'PICTURE IMPACT'], nb: 4 },
  { num: '625', label: 'Défraiement, gasoil', nature: 'depense', mots: ['TOTAL', 'DEFRAIEMENT'], nb: 5 },
  { num: '6257', label: 'Réception, sortie', nature: 'depense', mots: ['CARREFOUR', 'AUCHAN', 'RELAIS', 'CAFE BLEU'], nb: 8 },
  { num: '627', label: 'Services bancaires', nature: 'depense', mots: ['FACT SGT', 'COTIS', 'FRAIS'], nb: 12 },
  { num: '651', label: 'SACEM / SPRE', nature: 'depense', evenement: 'gala', mots: ['SACEM', 'SPRE'], nb: 2 },
  { num: '756', label: 'Cotisations', nature: 'recette', mots: ['COTISATION'], nb: 4 },
  { num: '7561', label: 'Participation au gala', nature: 'recette', evenement: 'gala', mots: ['GALA'], nb: 4 },
  { num: '7563', label: 'Entrées Galli', nature: 'recette', evenement: 'gala', mots: ['ENTREE'], nb: 2 },
  { num: '7567', label: 'Cours', nature: 'recette', mots: ['REM CHQ', 'HELLOASSO'], nb: 14 },
  { num: '768', label: 'Intérêts du livret', nature: 'recette', mots: ['INTERET'], nb: 1 },
  { num: '401', label: 'Fournisseurs', nature: 'tiers', solde: 'à payer : 345,07 €' },
  { num: '411', label: 'Adhérents', nature: 'tiers', solde: 'à recevoir : 100,00 €' },
  { num: '4671', label: 'Honoraires Revelles', nature: 'tiers', solde: 'soldé' },
  { num: '46711', label: 'Honoraires De Luca', nature: 'tiers', solde: 'soldé' },
  { num: '4672', label: 'Honoraires Pesenti', nature: 'tiers', solde: 'soldé' },
  { num: '4679', label: 'Honoraires Thomas', nature: 'tiers', solde: 'soldé' },
  { num: '471', label: "Compte d'attente", nature: 'attente', solde: '717,50 €' },
]

export const NATURES = {
  depense: 'Dépenses',
  recette: 'Recettes',
  tiers: 'Tiers (niveau Complet)',
  attente: 'Attente (niveau Complet)',
}

const sansAccents = (s) =>
  s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toUpperCase()

// Compte proposé pour une ligne de banque, d'après ses mots-clés ; null si
// rien ne correspond (« Compte à choisir »).
export function proposerCompte(libelle, montant) {
  const texte = sansAccents(libelle ?? '')
  const candidats = PLAN.filter((c) => (montant < 0 ? c.nature === 'depense' : c.nature === 'recette'))
  return candidats.find((c) => c.mots.some((m) => texte.includes(m))) ?? null
}

// Pièces d'exemple. etat : a_rattacher | rattachee | non_payee | especes.
export const PIECES = [
  {
    id: 'p1',
    dossier: 'achats',
    titre: 'Castorama · 121,19 €',
    detail: 'Facture F205034 du 02/06/2025',
    photo: 'Facture Castorama',
    compte: '6063',
    etat: 'a_rattacher',
    proposition: { libelle: 'CB 0206 CASTORAMA', montant: -121.19, date: '2025-06-04', pourquoi: 'même montant, 2 jours après' },
  },
  {
    id: 'p2',
    dossier: 'honoraires',
    titre: 'Revelles · 678,00 €',
    detail: "Note d'honoraires de mai 2025",
    photo: 'Note Revelles',
    compte: '6226',
    etat: 'a_rattacher',
    proposition: { libelle: 'VIR FACT REVELLES', montant: -678, date: '2025-06-03', pourquoi: 'compte 403, même montant' },
  },
  {
    id: 'p3',
    dossier: 'achats',
    titre: 'Théâtre Galli · 3 504,58 €',
    detail: 'Facture du 05/05/2025',
    photo: 'Facture Galli',
    compte: '613',
    etat: 'a_rattacher',
    proposition: null,
  },
  {
    id: 'p4',
    dossier: 'ventes',
    titre: 'Remise de chèques du 03/05/2025 · 3 795,00 €',
    detail: 'Ticket CIC (25 chèques) + page du cahier',
    photo: 'Ticket + cahier',
    compte: '7567',
    etat: 'a_rattacher',
    proposition: { libelle: 'REM CHQ', montant: 3795, date: '2025-05-03', pourquoi: 'même jour, même montant, compte 403' },
    cheques: [
      { nom: 'Charlot', famille: 'Famille Charlot', montant: 130 },
      { nom: 'Perquis Slimane', famille: 'Famille Perquis', montant: 130 },
      { nom: 'De Carlo', famille: 'Famille De Carlo', montant: 140 },
      { nom: 'Pommeret', famille: 'Famille Pommeret', montant: 380 },
      { nom: 'Barbière', famille: 'Famille Barbière', montant: 160 },
      { nom: '… 20 autres chèques', famille: '', montant: 2855 },
    ],
  },
  { id: 'p5', dossier: 'achats', titre: 'Amazon · 39,90 €', detail: 'Facture F23734340 du 09/02/2025 · « Tapis de danse enfants ×2 »', photo: 'Facture Amazon', compte: '6063', etat: 'rattachee', ligne: 'CB 0902 AMAZON −39,90 € le 10/02/2025' },
  { id: 'p6', dossier: 'honoraires', titre: 'Pesenti · 1 850,00 €', detail: "Note d'honoraires d'avril 2025", photo: 'Note Pesenti', compte: '6226', etat: 'rattachee', ligne: 'VIR FACT PESENTI −1 850,00 € le 02/05/2025' },
  { id: 'p7', dossier: 'notes_frais', titre: 'Patricia Hess · 227,00 €', detail: 'Note de frais « Travaux de couture », validée le 25/04/2025', photo: 'Note de frais', compte: '6228', etat: 'rattachee', ligne: 'VIR TRAVAUX COUTURE −227,00 € le 27/04/2025' },
  { id: 'p8', dossier: 'ventes', titre: 'Entrées Galli en espèces · 1 534,00 €', detail: 'Feuille de caisse du 29/06/2025', photo: 'Feuille de caisse', compte: '7563', etat: 'especes', ligne: 'Caisse, 29/06/2025' },
  { id: 'p9', dossier: 'ventes', titre: 'HelloAsso · 2 598,00 €', detail: 'Virement du 18/05/2025 · 300,00 € Cotisations + 2 298,00 € Cours (inscriptions)', photo: 'HelloAsso', compte: '7567', etat: 'rattachee', ligne: 'VIR HELLOASSO +2 598,00 € le 18/05/2025' },
]

// Les quatre dossiers créés par la trésorière dans Docs › Privé › Saison ›
// Financier (spec §8.3) ; « À rattacher » est un filtre, pas un dossier.
export const DOSSIERS = [
  { id: 'virements', label: 'Virements' },
  { id: 'a_rattacher', label: 'À rattacher' },
  { id: 'achats', label: 'Achats' },
  { id: 'honoraires', label: 'Honoraires' },
  { id: 'notes_frais', label: 'Notes de frais' },
  { id: 'ventes', label: 'Ventes' },
]

// Pièce d'exemple affichée sur une ligne de banque (fiche d'une opération).
export function pieceDeLaLigne(libelle) {
  const texte = sansAccents(libelle ?? '')
  if (texte.includes('AMAZON')) return PIECES[4]
  if (texte.includes('PESENTI')) return PIECES[5]
  if (texte.includes('COUTURE')) return PIECES[6]
  if (texte.includes('HELLOASSO')) return PIECES[8]
  return null
}

// Caisse : le seul compte saisi à la main (§8.5).
export const CAISSE = {
  solde: 1069.29,
  au: '2025-08-16',
  lignes: [
    { date: '2025-08-16', libelle: 'Remboursement Julien (erreur de virement)', montant: -750, compte: '471', piece: true },
    { date: '2025-06-29', libelle: 'Entrées Galli en espèces', montant: 1534, compte: '7563', piece: true },
    { date: '2025-06-29', libelle: 'Défraiement Thomas', montant: -100, compte: '625', piece: true },
    { date: '2025-06-29', libelle: 'Défraiement Revelles', montant: -100, compte: '625', piece: true },
    { date: '2025-06-29', libelle: 'Défraiement De Luca', montant: -60, compte: '625', piece: true },
    { date: '2025-06-18', libelle: 'Fond de caisse (retrait au distributeur)', montant: 200, compte: null, virement: 'depuis Compte 401', piece: false },
    { date: '2024-09-01', libelle: 'Solde de départ', montant: 345.29, compte: null, piece: false },
  ],
}

// Soldes de départ 2025-26, repris de la Balance 2024-25 (§8.7).
export const SOLDES_DEPART = [
  { num: '110', label: 'Report à nouveau', montant: 5926.24 },
  { num: '129', label: 'Résultat 2024-25 (perte)', montant: -310.35 },
  { num: '401', label: 'Fournisseurs à payer', montant: 345.07 },
  { num: '411', label: 'Adhérents à recevoir', montant: 100 },
  { num: '471', label: "Compte d'attente", montant: 717.5 },
  { num: '5123', label: 'CIC compte 401', montant: 3335.61 },
  { num: '5124', label: 'CIC compte 403', montant: 87.72 },
  { num: '5125', label: 'Livret', montant: 650.84 },
  { num: '530', label: 'Caisse', montant: 1069.29 },
]

// Synthèse Dépenses-Recettes 2024-25, forme du modèle Excel de la trésorière.
export const SYNTHESE = {
  charges: [
    { groupe: '60 · Achats', lignes: [['Autres fournitures', 1407.1], ['Fournitures administratives', 180.83], ['Tissus, accessoires', 837.63], ['Travaux de couture', 319.5]] },
    { groupe: '61 · Services extérieurs', lignes: [['Hébergement du site', 306.7], ['Assurance', 424.83], ['Entretien', 160]] },
    { groupe: '62 · Autres services extérieurs', lignes: [['Théâtre Galli, gala', 1600], ['Pompier, sécurité', 1744.58], ['Honoraires', 28709.5], ['Défraiement, gasoil', 395.3], ['Publicité, photos, cadeaux', 1173.23], ['Frais de réception', 659.05], ['Services bancaires', 265.18]] },
    { groupe: '63 · Impôts et taxes', lignes: [['SACEM / SPRE', 1001.13]] },
    { groupe: '65 · Autres charges', lignes: [['Charges diverses', 0.08]] },
  ],
  produits: [
    { groupe: '75 · Produits de gestion courante', lignes: [['Cotisations', 2916], ['Participation au gala', 3023], ['Entrées Galli', 4095], ['Cours', 28768], ['Divers', 0.71]] },
    { groupe: '76 · Produits financiers', lignes: [['Intérêts du livret', 71.58]] },
  ],
  totalCharges: 39184.64,
  totalProduits: 38874.29,
  resultat: -310.35,
  tresorerie: [['Compte courant 401', 3335.61], ['Compte courant 403', 87.72], ['Livret', 650.84], ['Caisse', 1069.29]],
  soldeTresorerie: 5143.46,
  fournisseursAPayer: 345.07,
  gala: { ressources: 7118, cout: 5672.84, benefice: 1445.16 },
}

export const DOCUMENTS_AG = [
  { id: 'synthese', titre: 'Synthèse Dépenses-Recettes', sous: 'compte de résultat par poste, trésorerie, fournisseurs à payer', formats: ['Voir', 'Excel'], niveau: 'simple' },
  { id: 'rapport', titre: 'Rapport financier', sous: "rédigé d'après le bilan et vos consignes ; chaque chiffre est placé par l'appli", formats: ['Word', 'PDF'], niveau: 'simple' },
  { id: 'grand_livre', titre: 'Grand livre', sous: 'toutes les opérations, par compte, avec le lien vers la pièce', formats: ['PDF'], niveau: 'complet' },
  { id: 'balance', titre: 'Balance', sous: 'totaux par compte', formats: ['PDF'], niveau: 'complet' },
  { id: 'honoraires', titre: 'Honoraires par professeur', sous: 'pour la déclaration DAS-2', formats: ['Excel'], niveau: 'complet' },
]

// Virements d'exemple (spec §8.3 bis). etat : a_payer | prepare | envoye | paye.
// rib : null quand il reste à photographier.
export const VIREMENTS = [
  { id: 'v1', etat: 'a_payer', nom: 'De Luca', objet: "Honoraires de mai 2025", montant: 720, compte: 'Compte courant 403 (honoraires)', piece: "Note d'honoraires de mai 2025", libelle: 'Contretemps honoraires mai 2025', rib: { titulaire: 'DE LUCA SARAH', iban: 'FR76 1027 8073 0000 0204 1450 176', par: 'la trésorière, le 12/09/2024' } },
  { id: 'v2', etat: 'a_payer', nom: 'Théâtre Galli', objet: 'Location pour le gala, facture du 05/05/2025', montant: 3504.58, compte: 'Compte courant 401', piece: 'Facture Galli', libelle: 'Contretemps gala 2025', rib: null },
  { id: 'v3', etat: 'a_payer', nom: 'Patricia Hess', objet: 'Note de frais « Fournitures », validée le 28/05/2025', montant: 45, compte: 'Compte courant 401', piece: 'Note de frais', libelle: 'Contretemps note de frais mai 2025', rib: { titulaire: 'HESS PATRICIA', iban: 'FR76 3000 4008 2800 0123 4567 890', par: 'Patricia Hess, le 25/04/2025' } },
  { id: 'v4', etat: 'prepare', nom: 'Thomas', objet: "Honoraires de mai 2025 · préparé par la trésorière le 01/06/2025", montant: 540, compte: 'Compte courant 403 (honoraires)', piece: "Note d'honoraires de mai 2025", libelle: 'Contretemps honoraires mai 2025', rib: { titulaire: 'THOMAS JULIE', iban: 'FR76 1695 8000 0112 3456 7890 123', par: 'la trésorière, le 03/10/2024' } },
  { id: 'v5', etat: 'envoye', nom: 'Pesenti', objet: 'Fait le 02/06/2025 · pas encore vu sur le compte', montant: 1790, compte: 'Compte courant 403 (honoraires)', piece: "Note d'honoraires de mai 2025", libelle: 'Contretemps honoraires mai 2025', rib: { titulaire: 'PESENTI MARC', iban: 'FR76 1820 6000 3065 4321 0987 654', par: 'la trésorière, le 12/09/2024' } },
  { id: 'v6', etat: 'paye', nom: 'Pesenti', objet: 'VIR FACT PESENTI −1 850,00 € le 02/05/2025', montant: 1850 },
  { id: 'v7', etat: 'paye', nom: 'Patricia Hess', objet: 'VIR TRAVAUX COUTURE −227,00 € le 27/04/2025', montant: 227 },
]
