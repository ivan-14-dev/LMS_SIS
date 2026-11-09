import {
  SchoolOutlined as School, PeopleOutline as People, AssignmentOutlined as Assignment,
  GradeOutlined as Grade, CalendarMonthOutlined as CalendarMonth, MoneyOutlined as Money,
  BookOutlined as Book, FlightOutlined as Flight, ScienceOutlined as Science,
  DescriptionOutlined as Description, GroupOutlined as Group, GavelOutlined as Gavel,
  BusinessOutlined as Business, PersonOutline as Person, AccountBalanceOutlined as AccountBalance,
  SettingsOutlined as Settings, ChildCareOutlined as ChildCare, ClassOutlined as Class,
  AssessmentOutlined as Assessment, EventNoteOutlined as EventNote, RestaurantOutlined as Restaurant,
  DirectionsBusOutlined as DirectionsBus, LocalHospitalOutlined as LocalHospital, HotelOutlined as Hotel,
  SportsEsportsOutlined as SportsEsports, GroupsOutlined as Groups, FaceOutlined as Face,
} from '@mui/icons-material';

const schoolManagers = ['direction', 'responsable_pedagogique'];
const schoolRegistry = [...schoolManagers, 'vie_scolaire'];
const universityManagers = ['president', 'vice_president', 'doyen', 'vice_doyen', 'directeur_etudes'];
const universityRegistry = [...universityManagers, 'scolarite', 'chef_departement'];
const teachers = ['enseignant', 'chercheur'];
const learnerRoles = ['eleve', 'etudiant', 'doctorant'];

const libraryModule = {
  path: 'bibliotheque',
  label: 'Bibliothèque',
  icon: Book,
  permission: 'bibliotheque.view_livre',
  alternatePermissions: [
    'bibliotheque.consulter_ressource_numerique', 'bibliotheque.change_livre',
    'bibliotheque.view_emprunt', 'bibliotheque.add_emprunt', 'bibliotheque.change_emprunt',
    'bibliotheque.view_reservation', 'bibliotheque.add_reservation', 'bibliotheque.change_reservation',
  ],
};

export const hasCapability = (capabilities, permission) => Boolean(
  permission && (capabilities?.permissions?.includes('*') || capabilities?.permissions?.includes(permission)),
);

export const hasActiveAffiliation = (capabilities, kind) => {
  const affiliations = capabilities?.affiliations || [];
  return Array.isArray(affiliations) && affiliations.some(
    affiliation => affiliation?.kind === kind && affiliation.active === true,
  );
};

const roleMatchesPortal = (role, kind) => {
  if (kind === 'learner') { return learnerRoles.includes(role); }
  if (kind === 'staff') { return ![...learnerRoles, 'parent'].includes(role); }
  return true;
};

export const canEnterPortal = (capabilities, kind) => roleMatchesPortal(capabilities?.role, kind)
  && hasActiveAffiliation(capabilities, kind)
  && capabilities?.portals?.[kind] !== false
  && (capabilities?.portals?.[kind] === true || hasCapability(capabilities, `portail.view_${kind}`));

export const workspaceKind = (capabilities) => {
  if (canEnterPortal(capabilities, 'learner') || canEnterPortal(capabilities, 'parent')) { return 'learner'; }
  if (canEnterPortal(capabilities, 'staff') && teachers.includes(capabilities?.role)) { return 'teacher'; }
  return 'administration';
};

export const canAccessModule = (item, capabilities) => Boolean(capabilities
  && (!item.module || (['sis.projects', 'sis.surveys', 'sis.events', 'sis.research', 'sis.practical_training'].includes(item.module)
    ? capabilities.modules?.[item.module] === true
    : capabilities.modules?.[item.module] !== false)) && (
  item.public
  || hasCapability(capabilities, item.permission)
  || item.alternatePermissions?.some(permission => hasCapability(capabilities, permission))
));

const schoolModules = [
  {
    title: 'Scolarité',
    items: [
      {
        path: 'eleves',
        label: 'Élèves',
        icon: ChildCare,
        permission: 'eleves.view_eleve',
        roles: [...schoolRegistry, 'enseignant'],
        resource: 'eleves',
        description: 'Dossiers, coordonnées et inscriptions des élèves.',
      },
      {
        path: 'classes',
        label: 'Classes',
        icon: Class,
        permission: 'classes.view_classe',
        roles: [...schoolRegistry, 'enseignant'],
        resource: 'classes/classes',
        description: 'Groupes, offres et inscriptions annuelles.',
      },
      {
        path: 'evaluations', label: 'Évaluations', icon: Assessment, permission: 'notes.view_evaluation', roles: ['direction', 'vie_scolaire', 'enseignant'],
      },
      {
        path: 'examens', label: 'Examens', icon: Description, permission: 'examens.view_sessionexamen', roles: schoolRegistry,
      },
      {
        path: 'bulletins', label: 'Bulletins', icon: Description, permission: 'notes.view_bulletin', roles: [...schoolRegistry, 'enseignant'],
      },
      {
        path: 'conseil-classe', label: 'Conseils de classe', icon: Groups, permission: 'conseil_classe.view_conseilclasse', roles: schoolRegistry,
      },
    ],
  },
  {
    title: 'Vie scolaire',
    items: [
      {
        path: 'presences', label: 'Présences', icon: EventNote, permission: 'presences.view_presence', roles: [...schoolRegistry, 'enseignant'],
      },
      {
        path: 'emploi-du-temps', label: 'Emploi du temps', icon: CalendarMonth, permission: 'emplois_du_temps.view_creneau', roles: [...schoolRegistry, 'enseignant'],
      },
      {
        path: 'discipline', label: 'Discipline', icon: Gavel, permission: 'discipline.view_incident', roles: schoolRegistry,
      },
    ],
  },
  {
    title: 'Services',
    items: [
      libraryModule,
      {
        path: 'cantine', label: 'Cantine', icon: Restaurant, permission: 'cantine.view_menu', roles: [...schoolRegistry, 'comptable'],
      },
      {
        path: 'transport', label: 'Transport', icon: DirectionsBus, permission: 'transport.view_lignetransport', roles: schoolRegistry,
      },
      {
        path: 'internat', label: 'Internat', icon: Hotel, permission: 'internat.view_batimentinternat', roles: schoolRegistry,
      },
      {
        path: 'infirmerie', label: 'Infirmerie', icon: LocalHospital, permission: 'infirmerie.view_visiteinfirmerie', roles: ['infirmier'],
      },
      {
        path: 'clubs', label: 'Clubs', icon: SportsEsports, permission: 'clubs.view_club', roles: [...schoolRegistry, 'enseignant'],
      },
    ],
  },
];

const universityModules = [
  {
    title: 'Scolarité',
    items: [
      {
        path: 'etudiants',
        label: 'Étudiants',
        icon: People,
        permission: 'etudiants.view_etudiant',
        roles: universityRegistry,
        resource: 'etudiants',
        description: 'Dossiers étudiants et parcours académiques.',
      },
      {
        path: 'formations',
        label: 'Formations',
        icon: School,
        permission: 'formations.view_formation',
        roles: universityRegistry,
        resource: 'formations/formations',
        description: 'Programmes, offres et organisation des apprentissages.',
      },
      {
        path: 'inscriptions',
        label: 'Inscriptions',
        icon: Assignment,
        permission: 'etudiants.view_inscriptionadministrative',
        roles: universityRegistry,
        resource: 'inscriptions',
        description: 'Inscriptions administratives et validations.',
      },
      {
        path: 'notes', label: 'Notes', icon: Grade, permission: 'notes.view_note', roles: [...teachers, 'scolarite', 'directeur_etudes'],
      },
      {
        path: 'examens', label: 'Examens', icon: Description, permission: 'examens.view_sessionexamen', roles: universityRegistry,
      },
      {
        path: 'jurys', label: 'Jurys', icon: Gavel, permission: 'jurys.view_jury', roles: universityRegistry,
      },
      {
        path: 'releves', label: 'Relevés', icon: Description, permission: 'releves.view_relevenotes', roles: universityRegistry,
      },
      {
        path: 'diplomes', label: 'Diplômes', icon: School, permission: 'diplomes.view_cessiondiplome', roles: universityRegistry,
      },
    ],
  },
  {
    title: 'Vie étudiante',
    items: [
      {
        path: 'emploi-du-temps', label: 'Emploi du temps', icon: CalendarMonth, permission: 'emplois_du_temps.view_creneaucours', roles: [...universityRegistry, ...teachers],
      },
      {
        path: 'bourses', label: 'Bourses', icon: Money, permission: 'bourses.view_attributionbourse', roles: [...universityRegistry, 'comptable'],
      },
      {
        path: 'stages', label: 'Stages', icon: Business, permission: 'stages.view_conventionstage', roles: universityRegistry,
      },
      {
        path: 'memoires', label: 'Mémoires', icon: Book, permission: 'memoires.view_memoire', roles: [...universityRegistry, ...teachers],
      },
      {
        path: 'mobilite', label: 'Mobilité', icon: Flight, permission: 'mobilite.view_candidaturemobilite', roles: universityRegistry,
      },
      libraryModule,
    ],
  },
  {
    title: 'Gestion',
    items: [
      {
        path: 'enseignants', label: 'Enseignants', icon: Person, permission: 'enseignants.view_enseignantchercheur', roles: universityRegistry,
      },
      {
        path: 'recherche',
        label: 'Recherche',
        icon: Science,
        module: 'sis.research',
        permission: 'recherche.gerer_recherche',
        alternatePermissions: [
          'recherche.consulter_recherche', 'recherche.contribuer_recherche', 'recherche.comptabiliser_recherche',
        ],
      },
      {
        path: 'paiements', label: 'Paiements', icon: Money, permission: 'paiements.view_paiementfrais', roles: ['comptable', 'scolarite', 'doyen'],
      },
    ],
  },
];

const administrativeModules = (variant) => {
  const roles = variant === 'secondaire' ? schoolManagers : universityManagers;
  return [
    {
      path: 'etablissement', label: 'Établissement', icon: AccountBalance, permission: `etablissement.change_${variant === 'secondaire' ? 'etablissement' : 'universite'}`, roles,
    },
    {
      path: 'annees-academiques', label: 'Années académiques', icon: CalendarMonth, permission: `etablissement.view_${variant === 'secondaire' ? 'anneescolaire' : 'anneeuniversitaire'}`, roles,
    },
    {
      path: 'utilisateurs', label: 'Utilisateurs', icon: People, permission: 'utilisateurs.view_utilisateur', alternatePermissions: ['auth.view_group'], roles,
    },
    {
      path: 'structure', label: 'Structure', icon: Business, permission: variant === 'secondaire' ? 'etablissement.view_niveau' : 'structure.view_departement', roles,
    },
    {
      path: 'integration-lms', label: 'Intégration LMS', icon: Science, permission: 'integration.view_outboxevent', roles,
    },
  ];
};

export const getNavigation = (type, variant, capabilities, search = '') => {
  const kind = workspaceKind(capabilities);
  const personalItems = [];
  personalItems.push({
    path: `/${variant}/stages-pratiques`,
    label: 'Stages pratiques',
    icon: Business,
    module: 'sis.practical_training',
    permission: 'stages.gerer_suivi_pratique',
    alternatePermissions: [
      'stages.consulter_suivi_pratique', 'stages.saisir_heures_pratiques',
      'stages.valider_heures_pratiques', 'stages.evaluer_competences_pratiques',
    ],
  });
  personalItems.push({
    path: `/${variant}/evenements`,
    label: 'Événements institutionnels',
    icon: CalendarMonth,
    module: 'sis.events',
    permission: 'core.consulter_evenement_institutionnel',
    alternatePermissions: ['core.gerer_evenement_institutionnel'],
  });
  if (capabilities?.modules?.['sis.surveys'] === true) {
    personalItems.push({
      path: `/${variant}/portail-enquetes`,
      label: 'Mes enquêtes institutionnelles',
      icon: Assignment,
      public: true,
      module: 'sis.surveys',
    });
  }
  if (capabilities?.modules?.['sis.projects'] === true) {
    personalItems.push({
      path: `/${variant}/projets`,
      label: learnerRoles.includes(capabilities?.role) ? 'Mes projets' : 'Projets pédagogiques',
      icon: Assignment,
      public: true,
      module: 'sis.projects',
    });
  }
  if (['eleve', 'etudiant', 'doctorant'].includes(capabilities?.role)
      || capabilities?.permissions?.some(permission => ['*', 'core.manage_accessdelegation'].includes(permission))) {
    personalItems.push({
      path: `/${variant}/missions`,
      label: kind === 'learner' ? 'Mes missions' : 'Accès délégués',
      icon: Assignment,
      public: true,
      module: 'sis.delegations',
    });
  }
  const documentRoles = variant === 'secondaire' ? ['eleve', 'parent'] : ['etudiant', 'doctorant'];
  if (documentRoles.includes(capabilities?.role)) {
    personalItems.push({
      path: `/${variant}/documents`, label: 'Mes documents', icon: Description, public: true,
    });
  }
  if (canEnterPortal(capabilities, 'learner')
      || (variant === 'secondaire' && canEnterPortal(capabilities, 'parent'))) {
    personalItems.push({
      path: `/${variant}/portail-apprenant`, label: capabilities.role === 'parent' ? 'Mes enfants' : 'Mon dossier', icon: Face, public: true,
    });
  }
  if (canEnterPortal(capabilities, 'staff')) {
    personalItems.push({
      path: `/${variant}/portail-staff`, label: 'Mon activité pédagogique', icon: Group, public: true,
    });
  }
  const sections = [{
    title: 'Mon espace',
    items: [
      {
        path: `/${variant}`, label: 'Accueil', icon: School, public: true, end: true,
      },
      ...personalItems,
      ...(kind !== 'learner' && capabilities?.permissions?.some(permission => [
        '*', 'core.request_signature', 'core.approve_signature', 'core.use_signature',
      ].includes(permission)) ? [{
          path: `/${variant}/signatures`, label: 'Signatures', icon: Description, public: true,
        }, {
          path: `/${variant}/archives`, label: 'Documents archivés', icon: Assignment, public: true,
        }] : []),
      ...(['eleve', 'etudiant', 'doctorant'].includes(capabilities?.role)
        || capabilities?.permissions?.some(permission => ['*', 'core.affecter_reclamation', 'core.traiter_reclamation'].includes(permission))
        ? [{
          path: `/${variant}/reclamations`, label: kind === 'learner' ? 'Mes réclamations' : 'Réclamations', icon: Assignment, public: true, module: 'sis.complaints',
        }] : []),
      {
        path: `/${variant}/workflows`, label: 'Notifications et suivi', icon: EventNote, public: true,
      },
    ],
  }];
  if (type !== 'admin') {
    (variant === 'secondaire' ? schoolModules : universityModules).forEach(section => sections.push({
      ...section,
      items: section.items.map(item => ({ ...item, path: `/${variant}/${item.path}` })),
    }));
  }
  const parameters = new URLSearchParams(search);
  parameters.set('sis', variant);
  sections.push({
    title: 'Administration',
    items: administrativeModules(variant).map(item => ({
      ...item, path: `/admin/${item.path}?${parameters}`,
    })),
  });
  sections.push({
    title: 'Compte',
    items: [{
      path: `/${variant}/compte`, label: 'Mon compte', icon: Settings, public: true,
    }],
  });
  return sections.map(section => ({
    ...section, items: section.items.filter(item => canAccessModule(item, capabilities)),
  })).filter(section => section.items.length);
};

export const filterNavigation = (sections, query) => {
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('fr');
  const term = normalize(query.trim());
  return sections.map(section => ({
    ...section,
    items: section.items.filter(item => normalize(`${section.title} ${item.label}`).includes(term)),
  })).filter(section => section.items.length);
};

export const matchesNavigation = (item, pathname) => {
  if (item.items) { return item.items.some(child => matchesNavigation(child, pathname)); }
  const path = item.path.split('?')[0];
  return pathname === path || (!item.end && pathname.startsWith(`${path}/`));
};

export const getWorkspaceGroups = (sections, kind) => {
  const available = sections.flatMap(section => section.items);
  const definitions = kind === 'learner' ? [
    {
      id: 'home', label: 'Accueil', icon: School, home: true,
    },
    {
      id: 'dossier', label: available.find(item => item.path.endsWith('/portail-apprenant'))?.label || 'Mon dossier', icon: Face, paths: ['portail-apprenant'],
    },
    {
      id: 'documents', label: 'Mes documents', icon: Description, paths: ['documents'],
    },
    {
      id: 'demarches', label: 'Mes démarches', icon: Assignment, paths: ['evenements', 'portail-enquetes', 'projets', 'missions', 'reclamations'],
    },
    {
      id: 'suivi', label: 'Notifications', icon: EventNote, paths: ['workflows'],
    },
  ] : [
    {
      id: 'home', label: 'Accueil', icon: School, home: true,
    },
    {
      id: 'scolarite', label: 'Scolarité', icon: People, paths: ['eleves', 'etudiants', 'classes', 'formations', 'inscriptions', 'enseignants'],
    },
    {
      id: 'pedagogie', label: 'Pédagogie', icon: Book, paths: ['portail-staff', 'portail-enquetes', 'projets', 'evaluations', 'notes', 'examens', 'jurys', 'conseil-classe', 'emploi-du-temps', 'memoires', 'recherche'],
    },
    {
      id: 'vie', label: 'Vie de l’établissement', icon: Groups, paths: ['evenements', 'presences', 'discipline', 'cantine', 'transport', 'internat', 'infirmerie', 'clubs', 'bourses', 'stages', 'mobilite', 'bibliotheque', 'paiements'],
    },
    {
      id: 'documents', label: 'Documents', icon: Description, paths: ['bulletins', 'releves', 'diplomes', 'signatures', 'archives'],
    },
    {
      id: 'suivi', label: 'Suivi et accès', icon: Assignment, paths: ['reclamations', 'missions', 'workflows'],
    },
    {
      id: 'administration', label: 'Administration', icon: Settings, admin: true,
    },
  ];
  const groups = definitions.map((group) => {
    const items = group.paths
      ? group.paths.map(path => available.find(item => item.path.split('?')[0].split('/').pop() === path)).filter(Boolean)
      : available.filter(item => (group.home ? item.end : item.path.startsWith('/admin/')));
    return {
      ...group, items, path: items[0]?.path, end: group.home,
    };
  }).filter(group => group.items.length);
  const grouped = new Set(groups.flatMap(group => group.items.map(item => item.path)));
  const additional = available.filter(item => !grouped.has(item.path) && !item.path.endsWith('/compte'));
  if (additional.length) {
    groups.push({
      id: 'assigned',
      label: 'Accès attribués',
      icon: Assignment,
      items: additional,
      path: additional[0].path,
    });
  }
  return groups;
};
