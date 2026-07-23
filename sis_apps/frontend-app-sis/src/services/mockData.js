/**
 * Mock data for SIS development and testing
 */

// Dashboard stats for supérieur
export const mockSuperieurDashboardStats = {
  etudiants: 12450,
  enseignants: 856,
  cours_actifs: 342,
  programmes: 78,
  inscriptions_semestre: 14520,
  taux_reussite: 85.4,
};

// Recent activities
export const mockRecentActivities = [
  { id: 1, type: 'inscription', message: 'Nouvel étudiant inscrit: Ahmed BENNANI', date: '2026-07-23T10:30:00Z' },
  { id: 2, type: 'note', message: 'Notes saisies pour Mathématiques L2', date: '2026-07-23T09:15:00Z' },
  { id: 3, type: 'paiement', message: 'Paiement reçu: 15000 MAD - Frais semestre', date: '2026-07-23T08:45:00Z' },
];

// Students list
export const mockEtudiants = [
  { id: 1, matricule: 'ETU-2026-001', nom: 'BENNANI', prenom: 'Ahmed', email: 'ahmed.bennani@univ.ma', filiere: 'Informatique', niveau: 'L2', statut: 'Inscrit' },
  { id: 2, matricule: 'ETU-2026-002', nom: 'ALAMI', prenom: 'Sara', email: 'sara.alami@univ.ma', filiere: 'Gestion', niveau: 'L3', statut: 'Inscrit' },
  { id: 3, matricule: 'ETU-2026-003', nom: 'IDRISSI', prenom: 'Omar', email: 'omar.idrissi@univ.ma', filiere: 'Économie', niveau: 'M1', statut: 'Inscrit' },
  { id: 4, matricule: 'ETU-2026-004', nom: 'CHRAIBI', prenom: 'Fatima', email: 'fatima.chraibi@univ.ma', filiere: 'Droit', niveau: 'L1', statut: 'En attente' },
  { id: 5, matricule: 'ETU-2026-005', nom: 'TAZI', prenom: 'Youssef', email: 'youssef.tazi@univ.ma', filiere: 'Informatique', niveau: 'M2', statut: 'Inscrit' },
];

// Courses list
export const mockCours = [
  { id: 1, code: 'INFO201', nom: 'Algorithmique Avancée', credits: 6, enseignant: 'Pr. BENALI', semestre: 'S3', etudiants_inscrits: 45 },
  { id: 2, code: 'INFO202', nom: 'Bases de données', credits: 4, enseignant: 'Pr. FASSI', semestre: 'S3', etudiants_inscrits: 52 },
  { id: 3, code: 'MATH201', nom: 'Analyse numérique', credits: 5, enseignant: 'Pr. TAHIRI', semestre: 'S3', etudiants_inscrits: 38 },
  { id: 4, code: 'LANG201', nom: 'Anglais technique', credits: 3, enseignant: 'Mme. SMITH', semestre: 'S3', etudiants_inscrits: 60 },
];

// Enseignants list
export const mockEnseignants = [
  { id: 1, matricule: 'ENS-001', nom: 'BENALI', prenom: 'Mohammed', email: 'm.benali@univ.ma', departement: 'Informatique', grade: 'Professeur' },
  { id: 2, matricule: 'ENS-002', nom: 'FASSI', prenom: 'Amina', email: 'a.fassi@univ.ma', departement: 'Informatique', grade: 'Maître de conférences' },
  { id: 3, matricule: 'ENS-003', nom: 'TAHIRI', prenom: 'Rachid', email: 'r.tahiri@univ.ma', departement: 'Mathématiques', grade: 'Professeur' },
];

// Filieres
export const mockFilieres = [
  { id: 1, code: 'INFO', nom: 'Sciences Informatiques', departement: 'Informatique', responsable: 'Pr. BENALI', etudiants: 450 },
  { id: 2, code: 'GEST', nom: 'Sciences de Gestion', departement: 'Gestion', responsable: 'Pr. ALAOUI', etudiants: 380 },
  { id: 3, code: 'ECO', nom: 'Sciences Économiques', departement: 'Économie', responsable: 'Pr. BERRADA', etudiants: 320 },
];

// Notes
export const mockNotes = [
  { id: 1, etudiant: 'Ahmed BENNANI', cours: 'Algorithmique Avancée', note_cc: 15.5, note_tp: 16, note_exam: 14, moyenne: 15.1, statut: 'Validé' },
  { id: 2, etudiant: 'Sara ALAMI', cours: 'Algorithmique Avancée', note_cc: 17, note_tp: 18, note_exam: 16.5, moyenne: 17.1, statut: 'Validé' },
  { id: 3, etudiant: 'Omar IDRISSI', cours: 'Bases de données', note_cc: 12, note_tp: 14, note_exam: 11, moyenne: 12.3, statut: 'Validé' },
];

// Inscriptions
export const mockInscriptions = [
  { id: 1, etudiant: 'Ahmed BENNANI', filiere: 'Informatique', annee: '2025-2026', semestre: 'S3', date_inscription: '2025-09-01', statut: 'Confirmée' },
  { id: 2, etudiant: 'Sara ALAMI', filiere: 'Gestion', annee: '2025-2026', semestre: 'S5', date_inscription: '2025-09-02', statut: 'Confirmée' },
];

// Dashboard stats for secondaire
export const mockSecondaireDashboardStats = {
  eleves: 1250,
  enseignants: 85,
  classes: 42,
  matieres: 15,
  taux_presence: 94.5,
  moyenne_generale: 13.8,
};

// Eleves secondaire
export const mockEleves = [
  { id: 1, matricule: 'ELV-2026-001', nom: 'BENMOUSSA', prenom: 'Karim', classe_nom: '2nde A', date_naissance: '2010-03-15', statut: 'Actif' },
  { id: 2, matricule: 'ELV-2026-002', nom: 'FILALI', prenom: 'Leila', classe_nom: '1ère S', date_naissance: '2009-07-22', statut: 'Actif' },
  { id: 3, matricule: 'ELV-2026-003', nom: 'OUAZZANI', prenom: 'Mehdi', classe_nom: 'Term S', date_naissance: '2008-11-08', statut: 'Actif' },
];

// Classes secondaire
export const mockClasses = [
  { id: 1, nom: '2nde A', niveau: 'Seconde', filiere: 'Générale', effectif: 32, professeur_principal: 'M. ALAMI' },
  { id: 2, nom: '2nde B', niveau: 'Seconde', filiere: 'Générale', effectif: 30, professeur_principal: 'Mme. BENNIS' },
  { id: 3, nom: '1ère S', niveau: 'Première', filiere: 'Scientifique', effectif: 28, professeur_principal: 'M. FASSI' },
  { id: 4, nom: 'Term S', niveau: 'Terminale', filiere: 'Scientifique', effectif: 25, professeur_principal: 'M. TAHIRI' },
];

// Presences
export const mockPresences = [
  { id: 1, date: '2026-07-23', eleve: 'Karim BENMOUSSA', classe: '2nde A', statut: 'Présent', justifie: null },
  { id: 2, date: '2026-07-23', eleve: 'Leila FILALI', classe: '1ère S', statut: 'Absent', justifie: 'Maladie' },
  { id: 3, date: '2026-07-22', eleve: 'Mehdi OUAZZANI', classe: 'Term S', statut: 'Retard', justifie: null },
];

// Bulletins
export const mockBulletins = [
  { id: 1, eleve: 'Karim BENMOUSSA', classe: '2nde A', trimestre: 1, moyenne: 14.5, rang: 5, appreciation: 'Bon travail, peut mieux faire' },
  { id: 2, eleve: 'Leila FILALI', classe: '1ère S', trimestre: 1, moyenne: 16.2, rang: 2, appreciation: 'Excellent travail' },
];

// Evaluations
export const mockEvaluations = [
  { id: 1, titre: 'Contrôle Mathématiques', classe: '2nde A', matiere: 'Mathématiques', date: '2026-07-20', type: 'Devoir surveillé', moyenne_classe: 12.5 },
  { id: 2, titre: 'Interrogation Physique', classe: '1ère S', matiere: 'Physique', date: '2026-07-21', type: 'Interrogation', moyenne_classe: 13.8 },
];

// Admin - Etablissement
export const mockEtablissement = {
  nom: 'Université Mohammed V',
  type: 'Université',
  adresse: 'Avenue des Sciences, Rabat',
  telephone: '+212 537 77 88 99',
  email: 'contact@um5.ac.ma',
  directeur: 'Pr. Ahmed ALAOUI',
  annee_scolaire: '2025-2026',
  nb_facultes: 12,
  nb_etudiants: 45000,
};

// Admin - Utilisateurs
export const mockUtilisateurs = [
  { id: 1, username: 'admin', nom: 'Administrateur', email: 'admin@univ.ma', role: 'Administrateur', actif: true, derniere_connexion: '2026-07-23T08:00:00Z' },
  { id: 2, username: 'scolarite1', nom: 'Service Scolarité', email: 'scolarite@univ.ma', role: 'Scolarité', actif: true, derniere_connexion: '2026-07-22T16:30:00Z' },
  { id: 3, username: 'doyen_sciences', nom: 'Doyen Sciences', email: 'doyen.sciences@univ.ma', role: 'Doyen', actif: true, derniere_connexion: '2026-07-23T09:15:00Z' },
];

// Admin - Structure
export const mockStructure = {
  facultes: [
    { id: 1, nom: 'Faculté des Sciences', departements: 8, enseignants: 120, etudiants: 5000 },
    { id: 2, nom: 'Faculté de Droit', departements: 5, enseignants: 80, etudiants: 4200 },
    { id: 3, nom: 'Faculté de Médecine', departements: 10, enseignants: 150, etudiants: 3500 },
  ],
  departements: [
    { id: 1, nom: 'Informatique', faculte: 'Faculté des Sciences', chef: 'Pr. BENALI', enseignants: 25 },
    { id: 2, nom: 'Mathématiques', faculte: 'Faculté des Sciences', chef: 'Pr. TAHIRI', enseignants: 20 },
  ],
};

// Portail Etudiant
export const mockPortailEtudiant = {
  profil: {
    matricule: 'ETU-2026-001',
    nom: 'BENNANI',
    prenom: 'Ahmed',
    email: 'ahmed.bennani@univ.ma',
    filiere: 'Sciences Informatiques',
    niveau: 'Licence 2',
    photo: null,
  },
  notes: [
    { cours: 'Algorithmique Avancée', note: 15.5, credits: 6, statut: 'Validé' },
    { cours: 'Bases de données', note: 14.0, credits: 4, statut: 'Validé' },
    { cours: 'Analyse numérique', note: 12.5, credits: 5, statut: 'Validé' },
  ],
  emploi_du_temps: [
    { jour: 'Lundi', heure: '08:30-10:30', cours: 'Algorithmique', salle: 'A101' },
    { jour: 'Lundi', heure: '14:00-16:00', cours: 'TP Bases de données', salle: 'Labo 3' },
    { jour: 'Mardi', heure: '10:30-12:30', cours: 'Analyse numérique', salle: 'B205' },
  ],
  solde_scolarite: 5000,
  credits_valides: 45,
  credits_requis: 180,
};
