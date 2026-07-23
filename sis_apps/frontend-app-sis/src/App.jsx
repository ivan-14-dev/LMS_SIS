// SIS - Main App Component
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Helmet } from 'react-helmet';
import { getConfig } from '@edx/frontend-platform';

import Header from '@edx/frontend-component-header';
import Footer from '@edx/frontend-component-footer';

// Layout
import SISLayout from './components/layout/SISLayout';
import Sidebar from './components/layout/Sidebar';

// Dashboards
import DashboardSuperieur from './superieur/Dashboard';
import DashboardSecondaire from './secondaire/Dashboard';

// === SIS Supérieur Modules ===
import EtudiantsPage from './superieur/etudiants/EtudiantsPage';
import EtudiantDetailPage from './superieur/etudiants/EtudiantDetailPage';
import FormationsPage from './superieur/formations/FormationsPage';
import FormationDetailPage from './superieur/formations/FormationDetailPage';
import InscriptionsPage from './superieur/inscriptions/InscriptionsPage';
import NotesPage from './superieur/notes/NotesPage';
import ExamensPage from './superieur/examens/ExamensPage';
import BoursesPage from './superieur/bourses/BoursesPage';
import EmploiDuTempsPage from './superieur/emploi-du-temps/EmploiDuTempsPage';
import EnseignantsPage from './superieur/enseignants/EnseignantsPage';
import StagesPage from './superieur/stages/StagesPage';
import MemoiresPage from './superieur/memoires/MemoiresPage';
import RecherchePage from './superieur/recherche/RecherchePage';
import DiplomesPage from './superieur/diplomes/DiplomesPage';
import PaiementsPage from './superieur/paiements/PaiementsPage';
import BibliothequePage from './superieur/bibliotheque/BibliothequePage';
import MobilitePage from './superieur/mobilite/MobilitePage';
import JurysPage from './superieur/jurys/JurysPage';
import RelevesPage from './superieur/releves/RelevesPage';

// Portails Supérieur
import PortailEtudiant from './superieur/portails/PortailEtudiant';
import PortailEnseignant from './superieur/portails/PortailEnseignant';
import PortailScolarite from './superieur/portails/PortailScolarite';
import PortailDoyen from './superieur/portails/PortailDoyen';

// === SIS Secondaire Modules ===
import ElevesPage from './secondaire/eleves/ElevesPage';
import EleveDetailPage from './secondaire/eleves/EleveDetailPage';
import ClassesPage from './secondaire/classes/ClassesPage';
import EvaluationsPage from './secondaire/evaluations/EvaluationsPage';
import BulletinsPage from './secondaire/bulletins/BulletinsPage';
import PresencesPage from './secondaire/presences/PresencesPage';
import DisciplinePage from './secondaire/discipline/DisciplinePage';
import CantinePage from './secondaire/cantine/CantinePage';
import TransportPage from './secondaire/transport/TransportPage';
import InfirmeriePage from './secondaire/infirmerie/InfirmeriePage';
import InternatPage from './secondaire/internat/InternatPage';
import ClubsPage from './secondaire/clubs/ClubsPage';
import ConseilClassePage from './secondaire/conseil-classe/ConseilClassePage';

// Portails Secondaire
import PortailEleve from './secondaire/portails/PortailEleve';
import PortailParent from './secondaire/portails/PortailParent';
import PortailEnseignantSec from './secondaire/portails/PortailEnseignant';

// Administration
import EtablissementPage from './admin/etablissement/EtablissementPage';
import UtilisateursPage from './admin/utilisateurs/UtilisateursPage';
import StructurePage from './admin/structure/StructurePage';
import AnneesAcademiquesPage from './admin/annees-academiques/AnneesAcademiquesPage';
import AnneesAcademiquesPage from './admin/annees-academiques/AnneesAcademiquesPage';

const App = () => (
  <BrowserRouter basename={getConfig().PUBLIC_PATH}>
    <Helmet>
      <title>SIS - Système d'Information Scolaire</title>
    </Helmet>
    <div className="d-flex flex-column min-vh-100">
      <Header />
      <main className="flex-grow-1">
        <Routes>
          {/* Redirection par défaut */}
          <Route path="/" element={<Navigate to="/superieur" replace />} />

          {/* ============ SIS SUPÉRIEUR ============ */}
          <Route path="/superieur" element={<SISLayout type="superieur" />}>
            <Route index element={<DashboardSuperieur />} />
            
            {/* Gestion académique */}
            <Route path="etudiants" element={<EtudiantsPage />} />
            <Route path="etudiants/:id" element={<EtudiantDetailPage />} />
            <Route path="formations" element={<FormationsPage />} />
            <Route path="formations/:id" element={<FormationDetailPage />} />
            <Route path="inscriptions" element={<InscriptionsPage />} />
            <Route path="notes" element={<NotesPage />} />
            <Route path="examens" element={<ExamensPage />} />
            <Route path="jurys" element={<JurysPage />} />
            <Route path="releves" element={<RelevesPage />} />
            <Route path="diplomes" element={<DiplomesPage />} />

            {/* Vie étudiante */}
            <Route path="bourses" element={<BoursesPage />} />
            <Route path="emploi-du-temps" element={<EmploiDuTempsPage />} />
            <Route path="stages" element={<StagesPage />} />
            <Route path="memoires" element={<MemoiresPage />} />
            <Route path="mobilite" element={<MobilitePage />} />
            <Route path="bibliotheque" element={<BibliothequePage />} />

            {/* Personnel */}
            <Route path="enseignants" element={<EnseignantsPage />} />
            <Route path="recherche" element={<RecherchePage />} />

            {/* Finances */}
            <Route path="paiements" element={<PaiementsPage />} />

            {/* Portails */}
            <Route path="portail-etudiant" element={<PortailEtudiant />} />
            <Route path="portail-enseignant" element={<PortailEnseignant />} />
            <Route path="portail-scolarite" element={<PortailScolarite />} />
            <Route path="portail-doyen" element={<PortailDoyen />} />
          </Route>

          {/* ============ SIS SECONDAIRE ============ */}
          <Route path="/secondaire" element={<SISLayout type="secondaire" />}>
            <Route index element={<DashboardSecondaire />} />

            {/* Gestion académique */}
            <Route path="eleves" element={<ElevesPage />} />
            <Route path="eleves/:id" element={<EleveDetailPage />} />
            <Route path="classes" element={<ClassesPage />} />
            <Route path="evaluations" element={<EvaluationsPage />} />
            <Route path="bulletins" element={<BulletinsPage />} />
            <Route path="conseil-classe" element={<ConseilClassePage />} />

            {/* Vie scolaire */}
            <Route path="presences" element={<PresencesPage />} />
            <Route path="discipline" element={<DisciplinePage />} />
            <Route path="emploi-du-temps" element={<EmploiDuTempsPage />} />

            {/* Services */}
            <Route path="cantine" element={<CantinePage />} />
            <Route path="transport" element={<TransportPage />} />
            <Route path="infirmerie" element={<InfirmeriePage />} />
            <Route path="internat" element={<InternatPage />} />
            <Route path="clubs" element={<ClubsPage />} />

            {/* Portails */}
            <Route path="portail-eleve" element={<PortailEleve />} />
            <Route path="portail-parent" element={<PortailParent />} />
            <Route path="portail-enseignant" element={<PortailEnseignantSec />} />
          </Route>

          {/* ============ ADMINISTRATION COMMUNE ============ */}
          <Route path="/admin" element={<SISLayout type="admin" />}>
            <Route path="etablissement" element={<EtablissementPage />} />
            <Route path="utilisateurs" element={<UtilisateursPage />} />
            <Route path="structure" element={<StructurePage />} />
            <Route path="annees-academiques" element={<AnneesAcademiquesPage />} />
          </Route>
        </Routes>
      </main>
      <Footer />
    </div>
  </BrowserRouter>
);

export default App;
