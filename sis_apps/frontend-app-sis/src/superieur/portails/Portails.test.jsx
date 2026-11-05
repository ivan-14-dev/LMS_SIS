/* eslint-disable react/prop-types, react/function-component-definition -- simple rendering stubs */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { getNavigation } from '../../components/layout/navigation';
import LearnerPortal from './PortailApprenantFamille';
import StaffPortal from './PortailStaffAdmin';

jest.mock('@tanstack/react-query', () => ({ useQuery: jest.fn() }));
jest.mock('react-router-dom', () => ({ useNavigate: () => jest.fn() }));
jest.mock('../../components/auth/PermissionGuard', () => ({ useCapabilities: jest.fn() }));
jest.mock('../../components/common', () => ({
  PageHeader: ({ title, actions = [] }) => (
    <><h1>{title}</h1>{actions.map(action => <button key={action.label} type="button">{action.label}</button>)}</>
  ),
  SectionNavigator: ({ sections }) => sections.map(section => <section key={section.id}>{section.content}</section>),
  SISDataTable: ({ title }) => <div>{title}</div>,
  StatCard: ({ title }) => <div>{title}</div>,
  WorkflowNotificationsPanel: () => <div>Notifications</div>,
}));
jest.mock('../../components/common/RecordsTabs', () => () => <div>Mes dossiers</div>);

const capability = (kind, permissions = []) => ({
  role: kind === 'learner' ? 'etudiant' : 'enseignant',
  affiliations: [{ kind, active: true }],
  permissions,
  portals: { [kind]: true },
});
const enabledQueries = () => useQuery.mock.calls.map(([options]) => options.enabled);
const links = data => getNavigation('superieur', 'superieur', data).flatMap(section => section.items);

beforeEach(() => {
  jest.clearAllMocks();
  useQuery.mockReturnValue({ data: { statistiques: {} }, isLoading: false, isError: false });
});

it('does not load student records for a role without active affiliation and effective grant', () => {
  useCapabilities.mockReturnValue({ data: { role: 'etudiant', permissions: ['portail.view_learner'] } });
  render(<LearnerPortal />);
  expect(screen.getByText(/réservé aux étudiants affiliés/)).toBeInTheDocument();
  expect(enabledQueries()).toEqual([false, false]);
  expect(links({ role: 'etudiant', permissions: ['portail.view_learner'] })
    .some(item => item.path.endsWith('/portail-apprenant'))).toBe(false);
});

it('shows learner records with the grant and stops fetching them after revocation', () => {
  const data = capability('learner');
  useCapabilities.mockReturnValue({ data });
  const { rerender } = render(<LearnerPortal />);
  expect(screen.getByRole('heading', { name: 'Mon espace étudiant' })).toBeInTheDocument();
  expect(enabledQueries()).toEqual([true, true]);
  expect(links(data).some(item => item.path.endsWith('/portail-apprenant'))).toBe(true);
  useCapabilities.mockReturnValue({ data: { ...data, affiliations: [{ kind: 'learner', active: false }] } });
  rerender(<LearnerPortal />);
  expect(screen.getByText(/réservé aux étudiants affiliés/)).toBeInTheDocument();
  expect(enabledQueries().slice(-2)).toEqual([false, false]);
});

it('loads only the authorized staff view and hides unrelated shortcuts', () => {
  const data = capability('staff', ['notes.view_note']);
  useCapabilities.mockReturnValue({ data });
  const { rerender } = render(<StaffPortal />);
  expect(screen.getByRole('heading', { name: 'Mon activité pédagogique' })).toBeInTheDocument();
  expect(enabledQueries()).toEqual([true, true, false, false, false, false]);
  expect(screen.getByRole('button', { name: 'Saisir des notes' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Inscriptions' })).not.toBeInTheDocument();
  useCapabilities.mockReturnValue({ data: { ...data, portals: { staff: false } } });
  rerender(<StaffPortal />);
  expect(screen.getByText(/réservé au staff affilié/)).toBeInTheDocument();
  expect(enabledQueries().slice(-6)).toEqual([false, false, false, false, false, false]);
});

it('denies staff when capabilities cannot be loaded without requesting staff endpoints', () => {
  useCapabilities.mockReturnValue({ isError: true });
  render(<StaffPortal />);
  expect(screen.getByText(/Impossible de vérifier/)).toBeInTheDocument();
  expect(enabledQueries()).toEqual([false, false, false, false, false, false]);
});
