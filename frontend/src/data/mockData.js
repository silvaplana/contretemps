// Données d'exemple (en dur) pour la maquette front-end du rôle Admin.
// `BASE_URL` = le "base" de vite.config.js ('/contretemps/' en prod, '/' en
// dev) : nécessaire pour que les vidéos statiques (public/videos/) se
// trouvent aussi une fois déployées sous silvaplana.cloud/contretemps/.
const BASE_URL = import.meta.env.BASE_URL
// Pas d'appel réseau ici : tout vient de ce fichier, en attendant le backend
// (voir spec/SPEC.md section 6 pour le schéma de base visé).

export const currentUser = {
  id: 'admin1',
  type: 'admin',
  nom: 'Petit',
  prenom: 'Valérie',
  email: 'v.petit@contretemps.fr',
  initiales: 'VP',
}

// Rang de rôle, du plus faible au plus fort (voir spec §2.2 "règle de
// sécurité du switch de profil famille") : sert à savoir si passer d'un
// profil à l'autre est une montée en privilège (code redemandé) ou non.
export const ROLE_RANK = { eleve: 0, professeur: 1, admin: 2 }

// Profils de la même famille que currentUser, façon Netflix (spec §2.1) :
// comptes de la même école partageant le même email, avec bascule sans
// reconnexion (juste le code redemandé en cas de montée en privilège).
// En dur pour la maquette — le vrai calcul par email est pour le backend
// (voir §6.2). Jojo et Noa Petit sont les élèves e3 et e6 ci-dessous.
export const familleActuelle = [
  { ...currentUser },
  { id: 'e3', type: 'eleve', nom: 'Petit', prenom: 'Jojo', initiales: 'JP' },
  { id: 'e6', type: 'eleve', nom: 'Fabre', prenom: 'Noa', initiales: 'NF' },
]

// École actuelle (voir spec §5.1.5 et §6.1) : nom + 3 codes d'accès,
// modifiables par tout admin depuis Admin > Paramètres école. Une seule
// école en dur pour la maquette — le multi-écoles réel est pour le backend.
export const ecoleActuelle = {
  id: 'ecole1',
  nom: 'Contretemps',
  codeAccesAdmin: 'ADMIN2026',
  codeAccesProf: 'PROF2026',
  codeAccesEleve: 'ELEVE2026',
}

export const professeurs = [
  {
    id: 'p1',
    nom: 'Chevalier',
    prenom: 'Isabelle',
    email: 'i.chevalier@mail.com',
    coursIds: ['c1', 'c2'],
  },
  {
    id: 'p2',
    nom: 'Renard',
    prenom: 'Julien',
    email: 'j.renard@mail.com',
    coursIds: ['c3'],
  },
  {
    id: 'p3',
    nom: 'Moreau',
    prenom: 'Camille',
    email: 'c.moreau@mail.com',
    coursIds: ['c4'],
  },
]

export const cours = [
  {
    id: 'c1',
    nom: 'Jazz niveau moyen',
    jour: 'Mercredi',
    heureDebut: '17h00',
    heureFin: '18h30',
    salle: 'Salle 2',
    professeurId: 'p1',
  },
  {
    id: 'c2',
    nom: 'Jazz niveau avancé',
    jour: 'Mercredi',
    heureDebut: '18h30',
    heureFin: '20h00',
    salle: 'Salle 2',
    professeurId: 'p1',
  },
  {
    id: 'c3',
    nom: 'Eveil 5-7 ans',
    jour: 'Samedi',
    heureDebut: '10h00',
    heureFin: '11h00',
    salle: 'Salle 1',
    professeurId: 'p2',
  },
  {
    id: 'c4',
    nom: 'Contemporain',
    jour: 'Jeudi',
    heureDebut: '19h00',
    heureFin: '20h30',
    salle: 'Salle 1',
    professeurId: 'p3',
  },
]

// Champs élève (voir spec/SPEC.md §6.4) : plus de champ "parent" libre —
// remplacé par un contact d'urgence structuré (urgenceNom/Prenom/Lien) et
// des champs santé, alignés sur ce qu'un compte Élève porte lui-même
// (mineur ou majeur, il n'y a plus de compte "Parent" séparé, voir §2.1).
export const eleves = [
  {
    id: 'e1',
    nom: 'Dubois',
    prenom: 'Marianne',
    coursIds: ['c1'],
    statutPaiement: 'paye',
    montantTotalAnnee: 320,
    montantPaye: 320,
    commentaireAdmin: '',
    dateNaissance: '2014-03-12',
    urgenceNom: 'Dubois',
    urgencePrenom: 'Sophie',
    urgenceLien: 'Mère',
    telephone: '06 12 34 56 78',
    email: 's.dubois@mail.com',
    adresse: '4 rue des Lilas, Le Beausset',
    allergies: 'Fruits à coque.',
    traitementMedical: '',
    informationsImportantes: '',
    certificatMedical: true,
  },
  {
    id: 'e2',
    nom: 'Martin',
    prenom: 'Coco',
    coursIds: ['c1'],
    statutPaiement: 'en_cours',
    montantTotalAnnee: 320,
    montantPaye: 100,
    commentaireAdmin: 'Relancer paiement.',
    dateNaissance: '2013-11-02',
    urgenceNom: 'Martin',
    urgencePrenom: 'Nadia',
    urgenceLien: 'Mère',
    telephone: '06 22 11 09 87',
    email: 'n.martin@mail.com',
    adresse: '12 avenue du Château, Le Beausset',
    allergies: '',
    traitementMedical: '',
    informationsImportantes: '',
    certificatMedical: true,
  },
  {
    id: 'e3',
    nom: 'Petit',
    prenom: 'Jojo',
    coursIds: ['c3'],
    statutPaiement: 'paye',
    montantTotalAnnee: 280,
    montantPaye: 280,
    commentaireAdmin: '',
    dateNaissance: '2018-06-20',
    urgenceNom: 'Petit',
    urgencePrenom: 'Karim',
    urgenceLien: 'Père',
    telephone: '06 45 67 89 10',
    email: 'k.petit@mail.com',
    adresse: '3 chemin des Vignes, Le Beausset',
    allergies: '',
    traitementMedical: '',
    informationsImportantes: '',
    certificatMedical: false,
  },
  {
    id: 'e4',
    nom: 'Roux',
    prenom: 'Thomas',
    coursIds: ['c1', 'c2'],
    statutPaiement: 'paye',
    montantTotalAnnee: 480,
    montantPaye: 480,
    commentaireAdmin: '',
    dateNaissance: '2011-01-30',
    urgenceNom: 'Roux',
    urgencePrenom: 'Alice',
    urgenceLien: 'Mère',
    telephone: '06 33 44 55 66',
    email: 'a.roux@mail.com',
    adresse: '8 rue de la Gare, Le Beausset',
    allergies: '',
    traitementMedical: '',
    informationsImportantes: '',
    certificatMedical: true,
  },
  {
    id: 'e5',
    nom: 'Blanc',
    prenom: 'Léa',
    coursIds: ['c2'],
    statutPaiement: 'en_cours',
    montantTotalAnnee: 320,
    montantPaye: 0,
    commentaireAdmin: 'Rappel envoyé le 02/08.',
    dateNaissance: '2010-09-14',
    urgenceNom: 'Blanc',
    urgencePrenom: 'Julie',
    urgenceLien: 'Mère',
    telephone: '06 55 44 33 22',
    email: 'j.blanc@mail.com',
    adresse: '21 impasse des Oliviers, Le Beausset',
    allergies: '',
    traitementMedical: 'Asthme (Ventoline dans le sac).',
    informationsImportantes: '',
    certificatMedical: true,
  },
  {
    id: 'e6',
    nom: 'Fabre',
    prenom: 'Noa',
    coursIds: ['c3'],
    statutPaiement: 'paye',
    montantTotalAnnee: 280,
    montantPaye: 280,
    commentaireAdmin: '',
    dateNaissance: '2017-12-05',
    urgenceNom: 'Petit',
    urgencePrenom: 'Karim',
    urgenceLien: 'Père',
    telephone: '06 45 67 89 10',
    email: 'k.petit@mail.com',
    adresse: '3 chemin des Vignes, Le Beausset',
    allergies: '',
    traitementMedical: '',
    informationsImportantes: '',
    certificatMedical: true,
  },
  {
    id: 'e7',
    nom: 'Simon',
    prenom: 'Inès',
    coursIds: ['c4'],
    statutPaiement: 'paye',
    montantTotalAnnee: 300,
    montantPaye: 300,
    commentaireAdmin: '',
    dateNaissance: '2009-04-18',
    urgenceNom: 'Simon',
    urgencePrenom: 'Marc',
    urgenceLien: 'Père',
    telephone: '06 66 77 88 99',
    email: 'm.simon@mail.com',
    adresse: '15 rue Jean Jaurès, Le Beausset',
    allergies: '',
    traitementMedical: '',
    informationsImportantes: '',
    certificatMedical: true,
  },
  {
    id: 'e8',
    nom: 'Girard',
    prenom: 'Maël',
    coursIds: ['c4'],
    statutPaiement: 'en_cours',
    montantTotalAnnee: 300,
    montantPaye: 150,
    commentaireAdmin: '',
    dateNaissance: '2008-07-22',
    urgenceNom: 'Girard',
    urgencePrenom: 'Elodie',
    urgenceLien: 'Mère',
    telephone: '06 77 88 99 00',
    email: 'e.girard@mail.com',
    adresse: '6 place du Marché, Le Beausset',
    allergies: '',
    traitementMedical: '',
    informationsImportantes: '',
    certificatMedical: false,
  },
]

export const groupes = [
  {
    id: 'g1',
    nom: 'Jazz niveau moyen',
    membres: [
      { type: 'professeur', id: 'p1' },
      { type: 'cours', id: 'c1' },
    ],
  },
  {
    id: 'g2',
    nom: 'Equipe pédagogique',
    membres: [
      { type: 'admin', id: 'admin1', label: 'Direction' },
      { type: 'professeur', id: 'p1' },
      { type: 'professeur', id: 'p2' },
    ],
  },
  {
    id: 'g3',
    nom: 'Spectacle fin d’année',
    membres: [
      { type: 'admin', id: 'admin1', label: 'Direction' },
      { type: 'cours', id: 'c2' },
      { type: 'cours', id: 'c4' },
    ],
  },
]

// Présences : par cours, une liste de dates et le statut de chaque élève à
// chaque date ('present' | 'absent' | 'retard').
export const presencesParCours = {
  c1: {
    dates: ['03/08', '05/08', '07/08', '10/08', '12/08'],
    parEleve: {
      e1: ['present', 'present', 'absent', 'present', 'retard'],
      e2: ['present', 'present', 'present', 'present', 'present'],
      e4: ['absent', 'present', 'present', 'absent', 'present'],
    },
  },
  c2: {
    dates: ['03/08', '05/08', '07/08', '10/08', '12/08'],
    parEleve: {
      e4: ['present', 'present', 'present', 'retard', 'present'],
      e5: ['present', 'absent', 'present', 'present', 'present'],
    },
  },
  c3: {
    dates: ['02/08', '09/08', '16/08'],
    parEleve: {
      e3: ['present', 'absent', 'present'],
      e6: ['present', 'present', 'retard'],
    },
  },
  c4: {
    dates: ['06/08', '13/08', '20/08'],
    parEleve: {
      e7: ['present', 'present', 'present'],
      e8: ['retard', 'present', 'absent'],
    },
  },
}

// Pas de champ "videos" ici : les vidéos d'une chorégraphie sont celles
// taguées avec son id dans videosParCours (voir plus bas) — gérées depuis
// l'onglet Vidéo, pas dupliquées ici.
export const choregraphiesParCours = {
  c1: [
    {
      id: 'ch1',
      nom: 'Comme un garçon',
      eleveIds: ['e1', 'e2', 'e4'],
      costume: 'Justaucorps noir, legging pailleté argent',
      horaireRepetition: 'Mercredi 17h00 - 18h30, salle 2',
    },
    {
      id: 'ch2',
      nom: 'Bang bang',
      eleveIds: ['e1', 'e2'],
      costume: 'Combinaison rouge',
      horaireRepetition: 'Vendredi 18h00 - 19h00, salle 1',
    },
  ],
  c2: [
    {
      id: 'ch3',
      nom: 'Naxos',
      eleveIds: ['e4', 'e5'],
      costume: 'Robe bleu nuit',
      horaireRepetition: 'Mercredi 20h00 - 20h30, salle 2',
    },
  ],
  c3: [],
  c4: [
    {
      id: 'ch4',
      nom: 'Silhouettes',
      eleveIds: ['e7', 'e8'],
      costume: 'Body noir uni',
      horaireRepetition: 'Jeudi 20h30 - 21h00, salle 1',
    },
  ],
}

// `choregraphieId` (nullable) tague la vidéo pour une chorégraphie du même
// cours (voir choregraphiesParCours ci-dessus) — utile pour retrouver toutes
// les vidéos d'une chorégraphie donnée.
export const videosParCours = {
  c1: [
    {
      id: 'v1',
      titre: 'Comme un garçon : détail début',
      datePublication: '05/08',
      duree: '01:20',
      description: '',
      url: `${BASE_URL}videos/comme-un-garcon-detail-debut.mp4`,
      choregraphieId: 'ch1',
    },
    {
      id: 'v1b',
      titre: 'Comme un garçon : final',
      datePublication: '05/08',
      duree: '01:05',
      description: '',
      choregraphieId: 'ch1',
    },
    {
      id: 'v2',
      titre: 'Bang bang (lent)',
      datePublication: '08/08',
      duree: '04:10',
      description: 'Passage à retravailler : le déplacement diagonal.',
      url: `${BASE_URL}videos/bang-bang-lent.mp4`,
      choregraphieId: 'ch2',
    },
  ],
  c2: [
    {
      id: 'v3',
      titre: 'Naxos — répétition',
      datePublication: '11/08',
      duree: '02:58',
      description: '',
      choregraphieId: 'ch3',
    },
  ],
  c3: [],
  c4: [
    {
      id: 'v4',
      titre: 'Silhouettes — filage',
      datePublication: '14/08',
      duree: '05:20',
      description: '',
      choregraphieId: 'ch4',
    },
  ],
}

export const conversations = [
  {
    id: 'conv1',
    type: 'groupe',
    nom: 'Jazz niveau moyen',
    messages: [
      {
        id: 'm1',
        auteur: 'Isabelle Chevalier',
        estMoi: false,
        contenu: 'Répét avancée à 17h30 mercredi prochain.',
        heure: '09:02',
        statut: 'vu',
        envoyeParMail: false,
      },
      {
        id: 'm2',
        auteur: 'Marianne',
        estMoi: false,
        contenu: 'Confirmez par mail ?',
        heure: '09:05',
        statut: 'vu',
        envoyeParMail: false,
      },
    ],
  },
  {
    id: 'conv2',
    type: 'individuelle',
    nom: 'Marianne (élève)',
    messages: [
      {
        id: 'm3',
        auteur: 'Marianne',
        estMoi: false,
        contenu: 'A quelle heure la répét de mercredi ?',
        heure: '09:02',
        statut: 'vu',
        envoyeParMail: false,
      },
      {
        id: 'm4',
        auteur: 'Valérie Petit',
        estMoi: true,
        contenu: '17h00 - 18h30, salle 2',
        heure: '09:15',
        statut: 'vu',
        envoyeParMail: true,
      },
    ],
  },
  {
    id: 'conv3',
    type: 'groupe',
    nom: 'Equipe pédagogique',
    messages: [
      {
        id: 'm5',
        auteur: 'Julien Renard',
        estMoi: false,
        contenu: 'Réunion planning la semaine prochaine ?',
        heure: 'Hier',
        statut: 'recu',
        envoyeParMail: false,
      },
    ],
  },
]

// Voir spec/SPEC.md §6.4 : 2 valeurs seulement (le détail des montants est
// dans montantTotalAnnee / montantPaye, pas dans le statut lui-même).
export const paiementLabels = {
  en_cours: 'En cours',
  paye: 'Payé',
}
