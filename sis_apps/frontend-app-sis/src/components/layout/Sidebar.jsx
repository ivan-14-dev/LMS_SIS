import React from 'react';
import PropTypes from 'prop-types';
import { NavLink, useLocation } from 'react-router-dom';
import { Icon } from '@openedx/paragon';
import {
  School, People, Assignment, Grade, CalendarMonth, Money, 
  Book, Flight, Science, Description, Group, Gavel,
  Business, Person, AccountBalance, Settings,
  ChildCare, Class, Assessment, EventNote, Restaurant,
  DirectionsBus, LocalHospital, Hotel, SportsEsports,
  Groups, FamilyRestroom, Face
} from '@openedx/paragon/icons';

const menuSuperieur = [
  {
    title: 'Gestion Académique',
    items: [
      { path: '/superieur/etudiants', label: 'Étudiants', icon: People },
      { path: '/superieur/formations', label: 'Formations', icon: School },
      { path: '/superieur/inscriptions', label: 'Inscriptions', icon: Assignment },
      { path: '/superieur/notes', label: 'Notes', icon: Grade },
      { path: '/superieur/examens', label: 'Examens', icon: Description },
      { path: '/superieur/jurys', label: 'Jurys', icon: Gavel },
      { path: '/superieur/releves', label: 'Relevés', icon: Description },
      { path: '/superieur/diplomes', label: 'Diplômes', icon: School },
      { path: '/superieur/workflows', label: 'Workflows', icon: EventNote },
    ],
  },
  {
    title: 'Vie Étudiante',
    items: [
      { path: '/superieur/bourses', label: 'Bourses', icon: Money },
      { path: '/superieur/emploi-du-temps', label: 'Emploi du temps', icon: CalendarMonth },
      { path: '/superieur/stages', label: 'Stages', icon: Business },
      { path: '/superieur/memoires', label: 'Mémoires', icon: Book },
      { path: '/superieur/mobilite', label: 'Mobilité', icon: Flight },
      { path: '/superieur/bibliotheque', label: 'Bibliothèque', icon: Book },
    ],
  },
  {
    title: 'Personnel',
    items: [
      { path: '/superieur/enseignants', label: 'Enseignants', icon: Person },
      { path: '/superieur/recherche', label: 'Recherche', icon: Science },
    ],
  },
  {
    title: 'Finances',
    items: [
      { path: '/superieur/paiements', label: 'Paiements', icon: Money },
    ],
  },
  {
    title: 'Portails',
    items: [
      { path: '/superieur/portail-etudiant', label: 'Portail Étudiant', icon: Face },
      { path: '/superieur/portail-enseignant', label: 'Portail Enseignant', icon: Person },
      { path: '/superieur/portail-scolarite', label: 'Portail Scolarité', icon: Group },
      { path: '/superieur/portail-doyen', label: 'Portail Doyen', icon: AccountBalance },
    ],
  },
];

const menuSecondaire = [
  {
    title: 'Gestion Académique',
    items: [
      { path: '/secondaire/eleves', label: 'Élèves', icon: ChildCare },
      { path: '/secondaire/classes', label: 'Classes', icon: Class },
      { path: '/secondaire/evaluations', label: 'Évaluations', icon: Assessment },
      { path: '/secondaire/bulletins', label: 'Bulletins', icon: Description },
      { path: '/secondaire/conseil-classe', label: 'Conseil de classe', icon: Groups },
      { path: '/secondaire/workflows', label: 'Workflows', icon: EventNote },
    ],
  },
  {
    title: 'Vie Scolaire',
    items: [
      { path: '/secondaire/presences', label: 'Présences', icon: EventNote },
      { path: '/secondaire/discipline', label: 'Discipline', icon: Gavel },
      { path: '/secondaire/emploi-du-temps', label: 'Emploi du temps', icon: CalendarMonth },
    ],
  },
  {
    title: 'Services',
    items: [
      { path: '/secondaire/cantine', label: 'Cantine', icon: Restaurant },
      { path: '/secondaire/transport', label: 'Transport', icon: DirectionsBus },
      { path: '/secondaire/infirmerie', label: 'Infirmerie', icon: LocalHospital },
      { path: '/secondaire/internat', label: 'Internat', icon: Hotel },
      { path: '/secondaire/clubs', label: 'Clubs', icon: SportsEsports },
    ],
  },
  {
    title: 'Portails',
    items: [
      { path: '/secondaire/portail-eleve', label: 'Portail Élève', icon: Face },
      { path: '/secondaire/portail-parent', label: 'Portail Parent', icon: FamilyRestroom },
      { path: '/secondaire/portail-enseignant', label: 'Portail Enseignant', icon: Person },
    ],
  },
];

const menuAdmin = [
  {
    title: 'Administration',
    items: [
      { path: '/admin/etablissement', label: 'Établissement', icon: AccountBalance },
      { path: '/admin/annees-academiques', label: 'Années académiques', icon: CalendarMonth },
      { path: '/admin/integration-lms', label: 'Intégration LMS', icon: Science },
      { path: '/admin/utilisateurs', label: 'Utilisateurs', icon: People },
      { path: '/admin/structure', label: 'Structure', icon: Settings },
    ],
  },
];

const Sidebar = ({ type }) => {
  const location = useLocation();

  const getMenu = () => {
    switch (type) {
      case 'superieur':
        return menuSuperieur;
      case 'secondaire':
        return menuSecondaire;
      case 'admin':
        return menuAdmin;
      default:
        return [];
    }
  };

  const getTitle = () => {
    switch (type) {
      case 'superieur':
        return 'SIS Supérieur';
      case 'secondaire':
        return 'SIS Secondaire';
      case 'admin':
        return 'Administration';
      default:
        return 'SIS';
    }
  };

  const menu = getMenu();

  return (
    <aside className="sis-sidebar">
      <div className="sis-sidebar__header">
        <h4>{getTitle()}</h4>
      </div>
      <nav className="sis-sidebar__nav">
        {menu.map((section) => (
          <div key={section.title} className="sis-sidebar__section">
            <div className="sis-sidebar__section-title">{section.title}</div>
            {section.items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `sis-sidebar__item ${isActive ? 'sis-sidebar__item--active' : ''}`
                }
              >
                <Icon src={item.icon} className="icon" />
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
};

Sidebar.propTypes = {
  type: PropTypes.oneOf(['superieur', 'secondaire', 'admin']).isRequired,
};

export default Sidebar;
