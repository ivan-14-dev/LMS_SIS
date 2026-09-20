# Frontend App SIS

Micro-frontend Open edX pour le Système d'Information Scolaire (SIS).

## 📋 Description

Cette application MFE (Micro Frontend) fournit une interface utilisateur moderne pour la gestion scolaire, couvrant :

- **SIS Supérieur** : Gestion universitaire (étudiants, formations, notes, bourses, etc.)
- **SIS Secondaire** : Gestion scolaire (élèves, classes, bulletins, présences, etc.)
- **Administration** : Configuration et gestion des utilisateurs

## 🛠️ Technologies

- React 18
- React Router 6
- @tanstack/react-query 5
- @openedx/paragon 22 (Design System Open edX)
- @edx/frontend-platform 8
- SCSS

## 🚀 Démarrage rapide

### Prérequis

- Node.js 18+
- npm ou yarn
- Instance LMS Open edX fonctionnelle

### Installation

```bash
cd /home/runner/work/LMS_SIS/LMS_SIS/sis_apps/frontend-app-sis

# Installer les dépendances
npm ci --legacy-peer-deps

# Configurer l'environnement
# Définir vos URLs et options dans .env.private (non versionné).
# .env.development fournit les valeurs locales par défaut.

# Lancer en développement
npm start
```

L'application sera disponible sur http://localhost:3000

Le verrou de dépendances actuel nécessite `--legacy-peer-deps` à l'installation
en raison d'un conflit de peer dependencies entre frontend-platform et frontend-build.

### Scripts disponibles

| Commande | Description |
|----------|-------------|
| `npm start` | Lance le serveur de développement |
| `npm run build` | Build de production |
| `npm run lint` | Vérification ESLint |
| `npm run lint:fix` | Correction automatique ESLint |
| `npm test` | Lance les tests Jest |
| `npm run i18n_extract` | Extraction des messages i18n |

## 📁 Structure du projet

```
src/
├── index.jsx           # Point d'entrée
├── App.jsx             # Routes principales
├── index.scss          # Styles globaux
├── i18n/               # Internationalisation
├── services/           # API et hooks
│   └── api.js          # Hooks React Query
├── components/
│   ├── common/         # Composants réutilisables
│   │   ├── StatCard.jsx
│   │   ├── SISDataTable.jsx
│   │   └── PageHeader.jsx
│   └── layout/         # Layout principal
│       ├── SISLayout.jsx
│       └── Sidebar.jsx
├── superieur/          # Pages SIS Supérieur
│   ├── Dashboard.jsx
│   ├── etudiants/
│   ├── formations/
│   ├── bourses/
│   └── portails/
├── secondaire/         # Pages SIS Secondaire
│   ├── Dashboard.jsx
│   ├── eleves/
│   ├── classes/
│   └── portails/
└── admin/              # Pages Administration
    ├── etablissement/
    ├── utilisateurs/
    └── structure/
```

## 🔧 Configuration

### Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `LMS_BASE_URL` | URL du LMS | `http://localhost:18000` |
| `SIS_SUPERIEUR_API_URL` | API SIS Supérieur | `http://localhost:8002/api/v1` |
| `SIS_SECONDAIRE_API_URL` | API SIS Secondaire | `http://localhost:8001/api/v1` |
| `SIS_ADMIN_API_URL` | API Administration | `http://localhost:8001/api/v1` |
| `USE_MOCK_API` | Données simulées uniquement si la valeur est `true` | `false` |

Les variables sont lues à la compilation par frontend-build, puis chargées par
l'initialisation frontend-platform. En développement, utiliser `.env.private` pour
les surcharges locales ; en production, fournir les variables de compilation ou
un fichier `.env` non versionné. Redémarrer le serveur ou reconstruire après modification.
Ne jamais placer de secret OAuth, de mot de passe ou de clé privée dans la configuration
du frontend : elle est accessible au navigateur.

### API réelles et démonstration

- **Par défaut**, l'application initialise frontend-platform et demande une connexion
  au LMS avant d'afficher les écrans. Les requêtes utilisent son client HTTP authentifié.
- **Démonstration seulement** : activer `USE_MOCK_API=true` dans la configuration locale.
  Ce mode ne demande pas de connexion LMS et affiche un avertissement permanent :
  les données sont fictives et les modifications ne sont pas enregistrées.
- Une erreur d'authentification ou d'API ne provoque jamais un basculement automatique
  vers les données simulées.

### Limites actuelles du parcours d'inscription

L'activation du client réel ne suffit **pas** à rendre l'inscription opérationnelle :

1. Les SIS utilisent actuellement l'authentification Django/DRF et SimpleJWT.
   L'authentification du navigateur auprès du LMS n'établit pas automatiquement une
   identité SIS. Il reste à réaliser et tester le raccordement sécurisé, avec validation
   des jetons et correspondance explicite avec l'utilisateur de l'établissement.
   Ne pas désactiver la vérification des signatures ni ouvrir les permissions pour
   contourner un refus d'accès.
2. Les routes du module d'inscriptions universitaires ne sont pas encore exposées,
   et le bouton « Nouvelle inscription » n'est pas raccordé.
3. Vérifier les routes et les contrats de données écran par écran, ainsi que les
   permissions, la pagination et la persistance après reconnexion.
4. Autoriser l'origine exacte du frontend dans la configuration CORS du LMS et des SIS ;
   configurer également les origines CSRF de confiance si l'authentification par session
   est utilisée. Déployer les services avec HTTPS en production.

Les tests frontend couvrent le choix explicite du mode, l'initialisation et les appels
HTTP ; ils ne constituent pas une validation de bout en bout LMS–SIS.

## 📦 Modules

### SIS Supérieur

- **Étudiants** : Gestion des dossiers étudiants
- **Formations** : Parcours, UE, ECUE
- **Inscriptions** : Inscriptions administratives et pédagogiques
- **Notes** : Saisie et consultation des notes
- **Examens** : Organisation des sessions d'examen
- **Bourses** : Demandes et attributions
- **Emploi du temps** : Planning des cours
- **Enseignants** : Gestion du personnel enseignant
- **Stages** : Suivi des stages
- **Mémoires** : Gestion des travaux de fin d'études
- **Recherche** : Laboratoires et projets
- **Diplômes** : Édition et suivi
- **Paiements** : Droits et frais de scolarité
- **Bibliothèque** : Emprunts et réservations
- **Mobilité** : Échanges internationaux
- **Jurys** : Délibérations
- **Relevés** : Édition des relevés de notes

### SIS Secondaire

- **Élèves** : Dossiers scolaires
- **Classes** : Organisation des classes
- **Évaluations** : Contrôles et devoirs
- **Bulletins** : Génération et impression
- **Présences** : Suivi des absences
- **Discipline** : Sanctions et incidents
- **Cantine** : Restauration scolaire
- **Transport** : Transport scolaire
- **Infirmerie** : Suivi médical
- **Internat** : Hébergement
- **Clubs** : Activités périscolaires
- **Conseil de classe** : Organisation et PV

### Portails

Espaces personnalisés pour chaque profil :
- Étudiant / Élève
- Enseignant
- Parent (secondaire)
- Scolarité
- Doyen / Direction

## 🧪 Tests

```bash
# Lancer tous les tests
npm test

# Avec couverture
npm test -- --coverage

# Mode watch
npm test -- --watch
```

## 🌐 Internationalisation

Les messages sont gérés via `@edx/frontend-platform/i18n`.

Pour ajouter/modifier des traductions :
1. Éditer `src/i18n/messages.js`
2. Extraire avec `npm run i18n_extract`

## 📄 Licence

Ce projet est sous licence AGPL-3.0, conformément à Open edX.
