import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { Alert, Card, CardHeader } from '@mui/material';
import PageHeader from './PageHeader';
import SISDataTable from './SISDataTable';
import WorkflowHistoryPanel from './WorkflowHistoryPanel';
import { useWorkflowHistory } from '../../services/api';
import AppearanceProvider from '../../theme/AppearanceProvider';
import RecordsTabs from './RecordsTabs';
import StatCard from './StatCard';
import SectionNavigator from './SectionNavigator';

jest.mock('../../services/api', () => ({ useWorkflowHistory: jest.fn() }));

it('preserves compact dashboard number hierarchy with the MUI theme', () => {
  render(
    <AppearanceProvider>
      <StatCard title="Élèves suivis" value={61} />
      <Card><CardHeader title="Notifications" /></Card>
    </AppearanceProvider>,
  );
  expect(screen.getByText('61')).toHaveStyle({ fontSize: '1.75rem', fontWeight: 700 });
  expect(screen.getByText('Élèves suivis')).toHaveStyle({ fontSize: '0.8125rem' });
});

const BrowserBack = () => {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate(-1)}>Précédent navigateur</button>;
};

const sections = [
  { id: 'notes', label: 'Notes', content: <p>Mes notes</p> },
  { id: 'bulletins', label: 'Bulletins', content: <p>Mes bulletins</p> },
];

it('opens a deep-linked section and preserves the institutional context and browser history', () => {
  render(
    <MemoryRouter initialEntries={['/admin/dossiers?sis=superieur&rubrique=bulletins']}>
      <SectionNavigator label="Dossiers" sections={sections} />
      <BrowserBack />
    </MemoryRouter>,
  );
  expect(screen.getByText('Mes bulletins')).toBeVisible();
  expect(screen.queryByText('Mes notes')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: 'Toutes les rubriques' }));
  expect(screen.queryByText('Mes bulletins')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Notes' })).toHaveAttribute('href', '/admin/dossiers?sis=superieur&rubrique=notes');
  fireEvent.click(screen.getByRole('link', { name: 'Notes' }));
  expect(screen.getByText('Mes notes')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Précédent navigateur' }));
  expect(screen.queryByText('Mes notes')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Précédent navigateur' }));
  expect(screen.getByText('Mes bulletins')).toBeVisible();
});

it('does not mount an unavailable section or interpret its identifier as a navigation target', () => {
  render(
    <MemoryRouter initialEntries={['/?rubrique=https%3A%2F%2Fexample.test']}>
      <SectionNavigator label="Dossiers" sections={sections} />
    </MemoryRouter>,
  );
  expect(screen.getByRole('alert')).toHaveTextContent('Cette rubrique n’est pas disponible');
  expect(screen.getAllByRole('link')).toHaveLength(2);
  expect(screen.queryByText('Mes notes')).not.toBeInTheDocument();
  expect(screen.queryByText('Mes bulletins')).not.toBeInTheDocument();
});

it('uses distinct status badges without discarding server labels or disguising unknown states', () => {
  render(
    <SISDataTable
      title="Admissions"
      columns={[{ Header: 'Statut', accessor: 'statut_display', Cell: () => 'Ancien affichage' }]}
      data={[
        { id: 1, statut: 'soumise', statut_display: 'Dossier soumis' },
        { id: 2, statut: 'en_instruction', statut_display: 'Instruction en cours' },
        { id: 3, statut: 'acceptee', statut_display: 'Admission acceptée' },
        { id: 4, statut: 'refusee', statut_display: 'Admission refusée' },
        { id: 5, statut: 'nouveau_code', statut_display: 'État institutionnel spécifique' },
      ]}
      searchable={false}
      exportable={false}
    />,
  );
  const labels = ['Dossier soumis', 'Instruction en cours', 'Admission acceptée', 'Admission refusée'];
  const tones = labels.map(label => screen.getByText(label).closest('.sis-status-badge').dataset.statusTone);
  expect(new Set(tones).size).toBe(4);
  expect(screen.getByText('État institutionnel spécifique').closest('.sis-status-badge')).toHaveAttribute('data-status-tone', 'neutral');
  expect(screen.queryByText('Ancien affichage')).not.toBeInTheDocument();
});

it('preserves computed status cells that do not contain a status code', () => {
  const signedStatus = ({ value }) => (value ? 'Signé' : 'Préparé');
  render(
    <SISDataTable
      title="Diplômes"
      columns={[{ Header: 'Statut', accessor: 'date_signature', Cell: signedStatus }]}
      data={[{ id: 1, date_signature: '2026-11-04T10:00:00Z' }, { id: 2, date_signature: null }]}
      searchable={false}
      exportable={false}
    />,
  );
  expect(screen.getByText('Signé')).toBeVisible();
  expect(screen.getByText('Préparé')).toBeVisible();
  expect(screen.queryByText('2026-11-04T10:00:00Z')).not.toBeInTheDocument();
  expect(screen.queryByText('Non renseigné')).not.toBeInTheDocument();
});

it.each([
  ['light', 'rgb(232, 240, 254)'],
  ['dark', 'rgb(25, 56, 76)'],
])('uses the shared semantic surface for rendered MUI alerts in %s mode', (mode, expected) => {
  render(<AppearanceProvider mode={mode}><Alert severity="info">Information institutionnelle</Alert></AppearanceProvider>);
  expect(screen.getByRole('alert')).toHaveStyle({ backgroundColor: expected });
});

it('keeps the breadcrumb target and exposes the back action', () => {
  render(
    <MemoryRouter>
      <PageHeader title="Dossier" showBack breadcrumbs={[{ label: 'Élèves', href: '/secondaire/eleves' }, { label: 'Dossier' }]} />
    </MemoryRouter>,
  );
  expect(screen.getByRole('link', { name: 'Élèves' })).toHaveAttribute('href', '/secondaire/eleves');
  expect(screen.getByRole('button', { name: 'Retour' })).toBeVisible();
});

it('labels search and permits keyboard activation without duplicating cell actions', () => {
  const onRowClick = jest.fn();
  render(
    <SISDataTable
      title="Classes"
      data={[{ id: 1, nom: '6e A' }]}
      columns={[{ Header: 'Nom', accessor: 'nom' }]}
      onRowClick={onRowClick}
    />,
  );
  expect(screen.getByRole('textbox', { name: 'Rechercher' })).toBeVisible();
  const row = screen.getByRole('row', { name: '6e A' });
  expect(row).toHaveAttribute('tabindex', '0');
  fireEvent.keyDown(row, { key: 'Enter' });
  expect(onRowClick).toHaveBeenCalledWith({ original: { id: 1, nom: '6e A' } });
  fireEvent.keyDown(screen.getByRole('cell', { name: '6e A' }), { key: 'Enter' });
  expect(onRowClick).toHaveBeenCalledTimes(1);
});

it('does not render a blank toolbar or heading for an embedded read-only table', () => {
  render(<SISDataTable title="" data={[]} columns={[{ Header: 'Nom', accessor: 'nom' }]} searchable={false} exportable={false} />);
  expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  expect(screen.getByRole('table', { name: 'Données' })).toBeVisible();
});

it('keeps an empty table message outside horizontally scrolling columns and hides empty pagination', () => {
  render(<SISDataTable title="Formations" data={[]} columns={[{ Header: 'Nom du cursus', accessor: 'nom' }]} />);
  expect(screen.getByRole('status')).toHaveTextContent('Aucune donnée disponible');
  expect(screen.getByRole('region', { name: 'Tableau : Formations' })).not.toHaveTextContent('Aucune donnée disponible');
  expect(screen.queryByText('Lignes par page:')).not.toBeInTheDocument();
});

it('restores table pagination after clearing a search with no matching rows', () => {
  render(<SISDataTable title="Classes" data={[{ id: 1, nom: '6e A' }]} columns={[{ Header: 'Nom', accessor: 'nom' }]} />);
  fireEvent.change(screen.getByRole('textbox', { name: 'Rechercher' }), { target: { value: 'absent' } });
  expect(screen.queryByText('Lignes par page:')).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole('textbox', { name: 'Rechercher' }), { target: { value: '' } });
  expect(screen.getByRole('row', { name: '6e A' })).toBeVisible();
  expect(screen.getByText('Lignes par page:')).toBeVisible();
});

it('opens one full-width dossier panel at a time and links keyboard-accessible tabs', () => {
  render(
    <RecordsTabs
      label="Mon dossier scolaire"
      panels={[
        { label: 'Notes', content: <p>Ma note publiée</p> },
        { label: 'Bulletins', content: <p>Mon bulletin publié</p> },
      ]}
    />,
  );
  expect(screen.getByRole('tabpanel', { name: 'Notes' })).toHaveTextContent('Ma note publiée');
  expect(screen.queryByText('Mon bulletin publié')).not.toBeInTheDocument();
  const notes = screen.getByRole('tab', { name: 'Notes' });
  notes.focus();
  fireEvent.keyDown(notes, { key: 'ArrowRight' });
  const bulletins = screen.getByRole('tab', { name: 'Bulletins' });
  expect(bulletins).toHaveFocus();
  fireEvent.click(bulletins);
  const panel = screen.getByRole('tabpanel', { name: 'Bulletins' });
  expect(bulletins).toHaveAttribute('aria-controls', panel.id);
  expect(panel).toHaveTextContent('Mon bulletin publié');
  expect(screen.queryByText('Ma note publiée')).not.toBeInTheDocument();
});

it('renders the Paragon history heading and distinguishes an error from an empty history', () => {
  useWorkflowHistory.mockReturnValue({ error: { response: { data: { detail: 'Historique indisponible.' } } } });
  render(<WorkflowHistoryPanel endpoint="historique/" title="Suivi du dossier" />);
  expect(screen.getByRole('heading', { name: 'Suivi du dossier', level: 2 })).toBeVisible();
  expect(screen.getByRole('alert')).toHaveTextContent('Historique indisponible.');
  expect(screen.queryByText('Aucun événement workflow disponible.')).not.toBeInTheDocument();
});
