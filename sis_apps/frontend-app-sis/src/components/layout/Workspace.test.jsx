import React from 'react';
import {
  fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useMediaQuery } from '@mui/material';
import { getConfig } from '@edx/frontend-platform';
import { fetchApi, useMarkAllWorkflowNotificationsRead, useWorkflowNotifications } from '../../services/api';
import SISLayout from './SISLayout';
import Sidebar from './Sidebar';
import WorkspaceTools from './WorkspaceTools';
import WorkspaceHome from './WorkspaceHome';
import WorkspaceCalendar from './WorkspaceCalendar';
import {
  canEnterPortal, getNavigation, getWorkspaceGroups, workspaceKind,
} from './navigation';
import SchoolLearnerPortal from '../../secondaire/portails/PortailApprenantFamille';
import UniversityLearnerPortal from '../../superieur/portails/PortailApprenantFamille';

jest.mock('@edx/frontend-platform', () => ({ getConfig: jest.fn() }));
jest.mock('@mui/material', () => ({ ...jest.requireActual('@mui/material'), useMediaQuery: jest.fn() }));
jest.mock('../auth/LocalSessionGate', () => jest.fn(({ children }) => children));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  useWorkflowNotifications: jest.fn(),
  useMarkAllWorkflowNotificationsRead: jest.fn(),
}));

let roles;
let failure;

const portalRole = (role, permissions = []) => {
  let kind = 'learner';
  if (role === 'parent') { kind = 'parent'; }
  if (role === 'enseignant') { kind = 'staff'; }
  return {
    role,
    permissions,
    affiliations: [{ kind, active: true }],
    portals: { [kind]: true },
  };
};

it.each([
  ['secondaire', 'eleve', 'staff', 'learner'],
  ['superieur', 'etudiant', 'staff', 'learner'],
  ['secondaire', 'enseignant', 'learner', 'teacher'],
  ['superieur', 'enseignant', 'learner', 'teacher'],
  ['secondaire', 'parent', 'staff', 'learner'],
])('ignores a stale %s / %s %s portal grant without losing the real workspace', (variant, role, staleKind, expectedKind) => {
  const valid = portalRole(role);
  const capabilities = {
    ...valid,
    affiliations: [...valid.affiliations, { kind: staleKind, active: true }],
    portals: { ...valid.portals, [staleKind]: true },
    permissions: ['*'],
  };
  expect(canEnterPortal(capabilities, staleKind)).toBe(false);
  expect(workspaceKind(capabilities)).toBe(expectedKind);
  const paths = getNavigation(variant, variant, capabilities).flatMap(section => section.items.map(item => item.path));
  expect(paths).toContain(`/${variant}/${expectedKind === 'teacher' ? 'portail-staff' : 'portail-apprenant'}`);
  expect(paths).not.toContain(`/${variant}/${staleKind === 'staff' ? 'portail-staff' : 'portail-apprenant'}`);
});

it.each([
  ['secondaire', 'eleve'],
  ['superieur', 'etudiant'],
  ['secondaire', 'super_admin'],
  ['superieur', 'super_admin'],
])('removes disabled missions from navigation without removing the account for %s / %s', (variant, role) => {
  const capabilities = {
    role,
    permissions: role === 'super_admin' ? ['*'] : [],
    modules: { 'sis.delegations': true },
  };
  const enabled = getNavigation(variant, variant, capabilities).flatMap(section => section.items);
  expect(enabled.some(item => item.path === `/${variant}/missions`)).toBe(true);
  const disabled = getNavigation(variant, variant, {
    ...capabilities, modules: { 'sis.delegations': false },
  }).flatMap(section => section.items);
  expect(disabled.some(item => item.path === `/${variant}/missions`)).toBe(false);
  expect(disabled.some(item => item.path === `/${variant}/compte`)).toBe(true);
});

it('navigates the real calendar across year boundaries', () => {
  jest.useFakeTimers().setSystemTime(new Date(2026, 11, 15, 12));
  try {
    render(<WorkspaceCalendar />);
    expect(screen.getByRole('heading', { name: 'décembre 2026' })).toBeVisible();
    expect(screen.getByLabelText('mardi 15 décembre 2026')).toHaveAttribute('aria-current', 'date');
    fireEvent.click(screen.getByRole('button', { name: 'Mois suivant' }));
    expect(screen.getByRole('heading', { name: 'janvier 2027' })).toBeVisible();
    expect(screen.queryByLabelText('mardi 15 décembre 2026')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mois précédent' }));
    expect(screen.getByLabelText('mardi 15 décembre 2026')).toHaveAttribute('aria-current', 'date');
  } finally {
    jest.useRealTimers();
  }
});

it('keeps the group editor reachable without account-view permission', () => {
  const sections = getNavigation('secondaire', 'secondaire', {
    role: 'group_manager', permissions: ['auth.view_group'],
  });
  const links = sections.flatMap(section => section.items);
  expect(links.find(item => item.label === 'Utilisateurs')?.path).toBe('/admin/utilisateurs?sis=secondaire');
  expect(links.some(item => item.label === 'Établissement')).toBe(false);
});

it('reports a failed institutional logo and allows a replacement image to load', () => {
  const { rerender } = render(
    <MemoryRouter><Sidebar sections={[]} branding={{ name: 'Campus', logo: '/logo.png' }} /></MemoryRouter>,
  );
  fireEvent.error(screen.getByAltText('Logo Campus'));
  expect(screen.getByRole('status')).toHaveTextContent('Logo indisponible.');
  expect(screen.queryByAltText('Logo Campus')).not.toBeInTheDocument();
  rerender(
    <MemoryRouter><Sidebar sections={[]} branding={{ name: 'Campus', logo: '/replacement.png' }} /></MemoryRouter>,
  );
  expect(screen.getByAltText('Logo Campus')).toHaveAttribute('src', '/replacement.png');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

const renderWorkspace = (path = '/secondaire') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })}>
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        {['secondaire', 'superieur'].map(variant => (
          <Route key={variant} path={`/${variant}`} element={<SISLayout type={variant} />}>
            <Route index element={<WorkspaceHome />} />
            <Route path="classes" element={<h1>Gestion des classes</h1>} />
            <Route path="eleves" element={<h1>Dossiers élèves</h1>} />
            <Route path="compte" element={<h1>Sécurité du compte</h1>} />
            <Route path="portail-apprenant" element={variant === 'secondaire' ? <SchoolLearnerPortal /> : <UniversityLearnerPortal />} />
          </Route>
        ))}
        <Route path="/admin" element={<SISLayout type="admin" />}>
          <Route path="etablissement" element={<h1>Paramètres institutionnels</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>
  </QueryClientProvider>,
);

beforeEach(() => {
  jest.clearAllMocks();
  window.localStorage.clear();
  roles = { secondaire: { role: 'super_admin', permissions: ['*'] }, superieur: { role: 'super_admin', permissions: ['*'] } };
  failure = '';
  useMediaQuery.mockReturnValue(false);
  getConfig.mockReturnValue({
    SIS_MODE: 'dual',
    SIS_SECONDAIRE_API_URL: 'https://secondaire.example.test/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superieur.example.test/api/v1',
  });
  useWorkflowNotifications.mockReturnValue({ data: [], isLoading: false });
  useMarkAllWorkflowNotificationsRead.mockReturnValue({ mutate: jest.fn() });
  fetchApi.mockImplementation(async (url) => {
    if (failure && url.includes(failure)) { throw new Error('Service indisponible'); }
    const variant = url.includes('secondaire.') ? 'secondaire' : 'superieur';
    if (url.endsWith('/capabilities/')) { return roles[variant]; }
    if (url.endsWith('/me/')) {
      return {
        id: 1,
        etablissement: 1,
        full_name: 'Compte recette',
        role_display: roles[variant].role,
        etablissement_nom: `Campus ${variant}`,
      };
    }
    if (url.endsWith('/tableau_bord/')) {
      return { statistiques: {}, eleve: { nom: 'Élève recette' }, etudiant: { nom: 'Étudiant recette' } };
    }
    if (url.includes('/portail/')) { return []; }
    if (url.includes('page_size=1')) { return { count: 0, results: [] }; }
    throw new Error(`Requête inattendue : ${url}`);
  });
});

it('replaces invented dashboard numbers with real zero counts and explicit errors', async () => {
  failure = '/classes/';
  renderWorkspace();
  expect(await screen.findByRole('heading', { name: 'Votre espace de travail' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'À consulter' })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText('0', { selector: 'strong' })).toBeInTheDocument());
  expect(await screen.findByText('Compteur indisponible.')).toBeInTheDocument();
  expect(fetchApi.mock.calls.some(([url]) => url.includes('/classes/classes/'))).toBe(true);
  expect(screen.queryByText('1,250')).not.toBeInTheDocument();
  expect(screen.queryByText(/2025-2026/)).not.toBeInTheDocument();
  expect(fetchApi.mock.calls.some(([url]) => url.includes('/dashboard/'))).toBe(false);
  failure = '';
  fireEvent.click(screen.getByRole('button', { name: 'Réessayer le compteur' }));
  await waitFor(() => expect(screen.queryByText('Compteur indisponible.')).not.toBeInTheDocument());
});

it.each([
  ['secondaire', 'eleve', 'Mon espace élève'],
  ['secondaire', 'parent', 'Mon espace famille'],
  ['superieur', 'etudiant', 'Mon espace étudiant'],
  ['superieur', 'doctorant', 'Mon espace étudiant'],
])('shows the personal workspace without administration for %s / %s', async (variant, role, heading) => {
  roles[variant] = portalRole(role);
  renderWorkspace(`/${variant}`);
  expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
  const navigation = within(screen.getByRole('navigation', { name: 'Navigation principale' }));
  expect(navigation.getAllByRole('link').length).toBeLessThanOrEqual(5);
  expect(navigation.queryByRole('link', { name: 'Utilisateurs' })).not.toBeInTheDocument();
  expect(navigation.queryByRole('link', { name: 'Notes' })).not.toBeInTheDocument();
  expect(navigation.getByRole('link', { name: role === 'parent' ? 'Mes enfants' : 'Mon dossier' })).toBeInTheDocument();
  expect(fetchApi.mock.calls.some(([url]) => url.includes('page_size=1'))).toBe(false);
  expect(screen.getByRole('region', { name: 'Modules disponibles' })).toBeVisible();
  expect(screen.getByRole('region', { name: 'Calendrier' })).toBeVisible();
  expect(screen.getByRole('region', { name: 'Suivi personnel' })).toBeVisible();
  fireEvent.click(screen.getByRole('link', { name: role === 'parent' ? 'Ouvrir Mes enfants' : 'Ouvrir Mon dossier' }));
  const documents = variant === 'secondaire' ? 'Bulletins publiés' : 'Relevés de notes';
  const tab = role === 'parent' ? 'Factures en attente' : documents;
  fireEvent.click(await screen.findByRole('tab', { name: tab, exact: true }));
  expect(screen.getByRole('table', { name: tab, exact: true })).toBeVisible();
  expect(screen.queryByRole('table', { name: role === 'parent' ? 'Enfants autorisés' : 'Notes récentes', exact: true })).not.toBeInTheDocument();
});

it.each(['secondaire', 'superieur'])('uses the %s teacher activity rather than administrative shortcuts', async (variant) => {
  roles[variant] = portalRole('enseignant');
  renderWorkspace(`/${variant}`);
  expect(await screen.findByRole('heading', { name: 'Mon activité pédagogique', level: 1 })).toBeInTheDocument();
  const navigation = within(screen.getByRole('navigation', { name: 'Navigation principale' }));
  expect(navigation.getByRole('link', { name: 'Pédagogie' })).toBeInTheDocument();
  expect(navigation.queryByRole('link', { name: 'Établissement' })).not.toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Modules disponibles' })).toBeVisible();
  expect(screen.getByRole('region', { name: 'Calendrier' })).toBeVisible();
  expect(screen.getByRole('region', { name: 'Suivi personnel' })).toBeVisible();
});

it('preserves learner permissions in primary navigation and the shared module board', async () => {
  roles.secondaire = portalRole('eleve', ['classes.view_classe']);
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Mon espace élève' });
  const navigation = within(screen.getByRole('navigation', { name: 'Navigation principale' }));
  expect(navigation.getByRole('link', { name: 'Accès attribués' })).toHaveAttribute('href', '/secondaire/classes');
  expect(screen.getByRole('link', { name: 'Ouvrir Classes' })).toBeVisible();
  expect(screen.queryByRole('link', { name: 'Ouvrir Élèves' })).not.toBeInTheDocument();
  expect(fetchApi.mock.calls.some(([url]) => url.includes('/eleves/'))).toBe(false);
  const grouped = getWorkspaceGroups(getNavigation('secondaire', 'secondaire', roles.secondaire), 'learner');
  expect(grouped.flatMap(group => group.items).filter(item => item.path === '/secondaire/classes')).toHaveLength(1);
});

it('pages and filters real authorized modules without keeping the old category page', async () => {
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Votre espace de travail' });
  expect(screen.getByRole('link', { name: 'Ouvrir Élèves' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Modules suivants' }));
  expect(screen.queryByRole('link', { name: 'Ouvrir Élèves' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'Scolarité' }));
  expect(screen.getByRole('link', { name: 'Ouvrir Élèves' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Modules précédents' })).toBeDisabled();
});

it('changes the shared theme directly without changing navigation permissions', async () => {
  roles.secondaire = portalRole('eleve');
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Mon espace élève' });
  const button = screen.getByRole('button', { name: 'Passer au thème sombre' });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(screen.getByRole('button', { name: 'Passer au thème clair' })).toBeVisible();
  const key = 'sis.workspace.v1:https://secondaire.example.test/api/v1/utilisateurs/comptes/:1:1';
  expect(JSON.parse(localStorage.getItem(key)).theme).toBe('dark');
  expect(screen.queryByRole('tab', { name: 'Administration' })).not.toBeInTheDocument();
});

it('preserves notification actions and delivery failures in the dashboard card', async () => {
  const markRead = jest.fn();
  useMarkAllWorkflowNotificationsRead.mockReturnValue({ mutate: markRead });
  useWorkflowNotifications.mockReturnValue({
    data: [{
      id: 1,
      title: 'Dossier à consulter',
      message: 'Une réponse est disponible.',
      category: 'Réclamation',
      event: { app_label: 'core', model: 'reclamation', object_id: 17 },
      metadata: { delivery: { email: { status: 'failed', last_error: 'Envoi refusé' } } },
    }],
    isLoading: false,
  });
  renderWorkspace();
  expect(await screen.findByRole('heading', { name: 'À consulter', level: 2 })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Consulter la réclamation' }))
    .toHaveAttribute('href', '/secondaire/reclamations?dossier=17');
  expect(screen.getByText('Email: Échec')).toBeVisible();
  expect(screen.getByText('Email: Envoi refusé')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Tout marquer comme lu' }));
  expect(markRead).toHaveBeenCalledTimes(1);
});

it('labels dashboard loading and keeps read actions unavailable while notifications load', async () => {
  useWorkflowNotifications.mockReturnValue({ isLoading: true });
  renderWorkspace();
  expect(await screen.findByRole('progressbar', { name: 'Chargement des notifications' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Tout marquer comme lu' })).not.toBeInTheDocument();
  expect(screen.queryByText('Aucune notification workflow non lue.')).not.toBeInTheDocument();
});

it('hides a disabled module even from administrators without hiding the mandatory services', async () => {
  roles.secondaire.modules = { 'sis.complaints': false };
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Votre espace de travail' });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir la palette de navigation' }));
  const palette = within(await screen.findByRole('dialog'));
  expect(palette.queryByRole('link', { name: 'Réclamations' })).not.toBeInTheDocument();
  expect(palette.getByRole('link', { name: 'Notifications et suivi' })).toBeInTheDocument();
});

it('honors specific permissions for a custom role and searches only visible modules', async () => {
  roles.secondaire = { role: 'accompagnement', permissions: ['notes.view_evaluation'] };
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Votre espace de travail' });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir la palette de navigation' }));
  const palette = within(await screen.findByRole('dialog'));
  fireEvent.change(palette.getByLabelText('Rechercher dans les modules autorisés'), { target: { value: 'evaluations' } });
  expect(palette.getAllByRole('link')).toHaveLength(1);
  expect(palette.getByRole('link', { name: 'Évaluations' })).toBeInTheDocument();
  fireEvent.change(palette.getByLabelText('Rechercher dans les modules autorisés'), { target: { value: 'utilisateurs' } });
  expect(palette.getByText('Aucun module autorisé ne correspond.')).toBeInTheDocument();
});

it('preserves accessible navigation labels when the desktop menu is collapsed', async () => {
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Votre espace de travail' });
  const home = within(screen.getByRole('navigation', { name: 'Navigation principale' })).getByRole('link', { name: 'Accueil' });
  expect(home).toHaveClass('sis-sidebar__item');
  expect(home).toHaveAttribute('aria-current', 'page');
  fireEvent.click(screen.getByRole('button', { name: 'Réduire le menu' }));
  expect(home).toHaveClass('sis-sidebar__item');
  expect(screen.getByRole('button', { name: 'Déployer le menu' })).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByLabelText('Rechercher un module')).not.toBeInTheDocument();
  expect(within(screen.getByRole('navigation', { name: 'Navigation principale' })).getByRole('link', { name: 'Scolarité' }))
    .toBeInTheDocument();
});

it.each([
  ['stages.view_conventionstage', 'Stages'],
  ['bibliotheque.view_emprunt', 'Bibliothèque'],
])('exposes the matching module for a custom role with %s', async (permission, label) => {
  roles.superieur = { role: 'accompagnement', permissions: [permission] };
  renderWorkspace('/superieur');
  await screen.findByRole('heading', { name: 'Votre espace de travail' });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir la palette de navigation' }));
  const palette = within(await screen.findByRole('dialog'));
  expect(palette.getByRole('link', { name: label })).toBeInTheDocument();
  expect(palette.queryByRole('link', { name: 'Étudiants' })).not.toBeInTheDocument();
});

it('opens a mobile dialog and closes it when a module is selected', async () => {
  useMediaQuery.mockReturnValue(true);
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Votre espace de travail' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir le menu' }));
  const menu = await screen.findByRole('dialog', { name: 'Menu de navigation' });
  fireEvent.click(within(menu).getByRole('link', { name: 'Scolarité' }));
  expect(await screen.findByRole('heading', { name: 'Dossiers élèves' })).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  fireEvent.click(within(screen.getByRole('navigation', { name: 'Navigation de section : Scolarité' }))
    .getByRole('link', { name: 'Classes' }));
  expect(await screen.findByRole('heading', { name: 'Gestion des classes' })).toBeInTheDocument();
});

it('keeps admin context explicit and reloads capabilities for the selected variant', async () => {
  renderWorkspace('/admin/etablissement?tab=profiles');
  expect(await screen.findByText('Campus secondaire')).toBeInTheDocument();
  const navigation = within(screen.getByRole('navigation', { name: 'Navigation principale' }));
  expect(navigation.getByRole('link', { name: 'Administration' })).toHaveAttribute('href', '/admin/etablissement?tab=profiles&sis=secondaire');
  roles.superieur = portalRole('etudiant');
  fireEvent.change(screen.getByLabelText('Contexte SIS'), { target: { value: 'superieur' } });
  expect(await screen.findByText('Campus superieur')).toBeInTheDocument();
  await waitFor(() => expect(navigation.queryByRole('link', { name: 'Utilisateurs' })).not.toBeInTheDocument());
});

it('does not turn capability failures into visible administrative modules', async () => {
  failure = '/capabilities/';
  renderWorkspace();
  expect(await screen.findByText(/Impossible de charger votre espace/)).toBeInTheDocument();
  expect(within(screen.getByRole('navigation', { name: 'Navigation principale' })).queryByRole('link')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Votre espace de travail' })).not.toBeInTheDocument();
});

it('reports personal data failures instead of displaying a successful empty portal', async () => {
  roles.superieur = portalRole('etudiant');
  failure = '/tableau_bord/';
  renderWorkspace('/superieur');
  expect(await screen.findByText(/Impossible de charger votre dossier/)).toBeInTheDocument();
  expect(screen.queryByText('Crédits validés')).not.toBeInTheDocument();
});

it('does not present a notification outage as an empty inbox', async () => {
  useWorkflowNotifications.mockReturnValue({ error: new Error('Service indisponible'), refetch: jest.fn() });
  renderWorkspace();
  expect(await screen.findByText(/Impossible de charger les notifications/)).toBeInTheDocument();
  expect(screen.queryByText('Aucune notification workflow non lue.')).not.toBeInTheDocument();
});

it('wraps keyboard navigation from the search input through the authorized links', async () => {
  render(
    <MemoryRouter>
      <WorkspaceTools
        sections={[{ title: 'Gestion', items: [{ path: '/first', label: 'Premier' }, { path: '/last', label: 'Dernier' }] }]}
        preferences={{
          theme: 'light', favorites: [], update: jest.fn(), ready: true, error: '',
        }}
      />
    </MemoryRouter>,
  );
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const dialog = within(await screen.findByRole('dialog', { name: 'Aller à un module' }));
  fireEvent.keyDown(dialog.getByLabelText('Rechercher dans les modules autorisés'), { key: 'ArrowUp' });
  expect(dialog.getByRole('link', { name: 'Dernier' })).toHaveFocus();
  fireEvent.keyDown(document.activeElement, { key: 'ArrowDown' });
  expect(dialog.getByRole('link', { name: 'Premier' })).toHaveFocus();
});

it('opens the keyboard palette, stores a favorite, and opens its authorized target', async () => {
  renderWorkspace('/admin/etablissement?sis=secondaire');
  await screen.findByText('Campus secondaire');
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const dialog = within(await screen.findByRole('dialog', { name: 'Aller à un module' }));
  fireEvent.change(dialog.getByLabelText('Rechercher dans les modules autorisés'), { target: { value: 'classes' } });
  fireEvent.click(dialog.getByRole('button', { name: 'Ajouter Classes aux favoris' }));
  expect(dialog.getByRole('button', { name: 'Retirer Classes des favoris' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(dialog.getByRole('link', { name: 'Classes', exact: true }));
  await screen.findByRole('heading', { name: 'Gestion des classes' });
  expect(within(screen.getByRole('navigation', { name: 'Navigation principale' }))
    .getByRole('link', { name: 'Scolarité' })).toHaveAttribute('aria-current', 'page');
  fireEvent.click(within(screen.getByRole('navigation', { name: 'Navigation principale' }))
    .getByRole('link', { name: 'Accueil' }));
  expect(within(await screen.findByRole('navigation', { name: 'Favoris' })).getByRole('link', { name: 'Classes' })).toBeVisible();
}, 15000);

it('keeps native LMS courses and logout available inside the shared ERP account menu', async () => {
  const config = getConfig();
  getConfig.mockReturnValue({
    ...config,
    SIS_AUTH_MODE: 'lms',
    LMS_BASE_URL: 'https://lms.example.test',
    LOGOUT_URL: 'https://lms.example.test/logout',
  });
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Votre espace de travail' });
  fireEvent.click(screen.getByRole('button', { name: 'Menu du compte' }));
  expect(await screen.findByRole('menuitem', { name: 'Mes cours LMS' })).toHaveAttribute('href', 'https://lms.example.test/dashboard');
  expect(screen.getByRole('menuitem', { name: 'Se déconnecter' })).toHaveAttribute('href', 'https://lms.example.test/logout');
});

it('does not expose inaccessible modules or navigate to forged stored URLs through favorites', async () => {
  const key = 'sis.workspace.v1:https://secondaire.example.test/api/v1/utilisateurs/comptes/:1:1';
  localStorage.setItem(key, JSON.stringify({
    theme: 'light', favorites: ['/secondaire/classes', 'https://untrusted.example/'],
  }));
  roles.secondaire = portalRole('eleve');
  renderWorkspace();
  await screen.findByRole('heading', { name: 'Mon espace élève' });
  expect(screen.queryByText('Favoris')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir la palette de navigation' }));
  expect(within(await screen.findByRole('dialog')).queryByRole('link', { name: 'Classes' })).not.toBeInTheDocument();
});

it('lets administrators reach business modules from the settings area without changing the tenant', async () => {
  renderWorkspace('/admin/etablissement?sis=secondaire');
  await screen.findByText('Campus secondaire');
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir la palette de navigation' }));
  const dialog = within(await screen.findByRole('dialog'));
  expect(dialog.getByRole('link', { name: 'Classes' })).toHaveAttribute('href', '/secondaire/classes');
  expect(dialog.getByRole('link', { name: 'Établissement' })).toHaveAttribute('href', '/admin/etablissement?sis=secondaire');
});

it.each(['secondaire', 'superieur'])('groups every authorized route once with at most seven primary links for %s', variant => {
  const sections = getNavigation(variant, variant, roles[variant]);
  const groups = getWorkspaceGroups(sections, 'administration');
  expect(groups.length).toBeLessThanOrEqual(7);
  const grouped = groups.flatMap(group => group.items.map(item => item.path));
  const expected = sections.flatMap(section => section.items).filter(item => !item.path.endsWith('/compte'))
    .map(item => item.path);
  expect(grouped.sort()).toEqual(expected.sort());
  expect(new Set(grouped).size).toBe(grouped.length);
});

it('keeps the active group and its sibling pages visible on a direct URL', async () => {
  renderWorkspace('/secondaire/classes');
  const main = within(await screen.findByRole('navigation', { name: 'Navigation principale' }));
  await waitFor(() => expect(main.getByRole('link', { name: 'Scolarité' })).toHaveAttribute('aria-current', 'page'));
  expect(main.queryByRole('link', { name: 'Classes' })).not.toBeInTheDocument();
  const local = within(screen.getByRole('navigation', { name: 'Navigation de section : Scolarité' }));
  expect(local.getByRole('link', { name: 'Classes' })).toHaveAttribute('aria-current', 'page');
  fireEvent.click(local.getByRole('link', { name: 'Élèves' }));
  expect(await screen.findByRole('heading', { name: 'Dossiers élèves' })).toBeVisible();
});
