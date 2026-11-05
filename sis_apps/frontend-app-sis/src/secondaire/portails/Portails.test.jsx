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
  role: kind === 'learner' ? 'eleve' : 'enseignant',
  affiliations: [{ kind, active: true }],
  permissions,
  portals: { [kind]: true },
});
const items = data => getNavigation('secondaire', 'secondaire', data).flatMap(section => section.items);
const enabledQueries = () => useQuery.mock.calls.map(([options]) => options.enabled);

beforeEach(() => {
  jest.clearAllMocks();
  useQuery.mockReturnValue({ data: { statistiques: {} }, isLoading: false, isError: false });
});

it('does not open the staff portal via a role alone, a disabled affiliation or unavailable capabilities', () => {
  useCapabilities.mockReturnValue({ data: { role: 'enseignant', permissions: [] }, isLoading: false });
  render(<StaffPortal />);
  expect(screen.getByText(/réservé au staff affilié/)).toBeInTheDocument();
  expect(enabledQueries()).toEqual([false, false, false]);
  expect(items({ role: 'enseignant', permissions: [] }).some(item => item.path.endsWith('/portail-staff'))).toBe(false);
  useCapabilities.mockReturnValue({ data: capability('staff'), isError: true });
  render(<StaffPortal />);
  expect(screen.getByText(/Impossible de vérifier/)).toBeInTheDocument();
  expect(enabledQueries().slice(-3)).toEqual([false, false, false]);
});

it('shows only effective staff actions and removes them on revocation', () => {
  const data = capability('staff', ['classes.view_classe']);
  useCapabilities.mockReturnValue({ data, isLoading: false });
  const { rerender } = render(<StaffPortal />);
  expect(screen.getByRole('heading', { name: 'Mon activité pédagogique' })).toBeInTheDocument();
  expect(enabledQueries()).toEqual([true, true, false]);
  expect(screen.queryByRole('button', { name: 'Présences' })).not.toBeInTheDocument();
  expect(items(data).some(item => item.path.endsWith('/portail-staff'))).toBe(true);
  useCapabilities.mockReturnValue({
    data: { ...data, affiliations: [{ kind: 'staff', active: false }] }, isLoading: false,
  });
  rerender(<StaffPortal />);
  expect(screen.getByText(/réservé au staff affilié/)).toBeInTheDocument();
  expect(enabledQueries().slice(-3)).toEqual([false, false, false]);
});

it('keeps learner and parent paths separate and disables revoked learner queries', () => {
  const learner = capability('learner');
  useCapabilities.mockReturnValue({ data: learner, isLoading: false });
  const { rerender } = render(<LearnerPortal />);
  expect(screen.getByRole('heading', { name: 'Mon espace élève' })).toBeInTheDocument();
  expect(enabledQueries()).toEqual([true, true, false]);
  useCapabilities.mockReturnValue({ data: capability('parent'), isLoading: false });
  rerender(<LearnerPortal />);
  expect(screen.getByRole('heading', { name: 'Mon espace famille' })).toBeInTheDocument();
  expect(enabledQueries().slice(-3)).toEqual([false, false, true]);
  useCapabilities.mockReturnValue({ data: { ...learner, portals: { learner: false } }, isLoading: false });
  rerender(<LearnerPortal />);
  expect(screen.getByText(/réservé aux élèves et parents affiliés/)).toBeInTheDocument();
  expect(enabledQueries().slice(-3)).toEqual([false, false, false]);
});
