import React from 'react';
import {
  fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchApi, patchApi, postApi } from '../../services/api';
import EtablissementPage from './EtablissementPage';

jest.setTimeout(30000);

const endpoint = 'https://sis.example/api/v1/etablissement/current/';
jest.mock('../../services/api', () => ({
  fetchApi: jest.fn(),
  patchApi: jest.fn(),
  postApi: jest.fn(),
  getCurrentEstablishmentUrl: () => 'https://sis.example/api/v1/etablissement/current/',
}));
jest.mock('../../components/common', () => ({
  PageHeader: () => <h1>Configuration établissement</h1>,
}));

const numeric = {
  mode: 'numeric', minimum: 0, maximum: 20, pass_mark: 10,
};
const competency = {
  mode: 'competency', criteria: [{ code: 'reading', label: 'Lecture' }],
};
const profiles = [
  ['primary', 'École primaire', 'annual', competency, null],
  ['secondary', 'Collège / lycée', 'annual', numeric, null],
  ['higher_education', 'Université / grande école', 'semester', numeric, { system: 'ECTS', target: 60 }],
  ['vocational', 'Formation professionnelle', 'session', competency, null],
  ['custom', 'Profil personnalisé', 'continuous', { mode: 'pass_fail' }, null],
].map(([code, label, calendar, assessment, credits]) => ({
  code,
  label,
  template: {
    code,
    label,
    profile: code,
    version: 1,
    calendar,
    assessment,
    credits,
    terminology: { learner: 'Apprenant', educator: 'Formateur', group: 'Groupe' },
  },
}));
const schema = {
  profiles,
  calendars: [
    { code: 'annual', label: 'Année scolaire' }, { code: 'semester', label: 'Semestres' },
    { code: 'session', label: 'Sessions courtes' }, { code: 'continuous', label: 'Rythme libre' },
  ],
  assessment_modes: [
    { code: 'numeric', label: 'Notes chiffrées' }, { code: 'competency', label: 'Compétences' },
    { code: 'pass_fail', label: 'Validé / non validé' },
  ],
  assessment_templates: { numeric, competency, pass_fail: { mode: 'pass_fail' } },
};
let institution;
const originalResizeObserver = global.ResizeObserver;
beforeAll(() => {
  global.ResizeObserver = jest.fn(() => ({ observe: jest.fn(), disconnect: jest.fn() }));
});
afterAll(() => {
  if (originalResizeObserver === undefined) {
    delete global.ResizeObserver;
  } else {
    global.ResizeObserver = originalResizeObserver;
  }
});
const show = () => render(
  <QueryClientProvider client={new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })}
  >
    <EtablissementPage />
  </QueryClientProvider>,
);
const select = async (container, label, option) => {
  fireEvent.mouseDown(container.getByRole('combobox', { name: label }));
  const menu = screen.getByRole('listbox');
  fireEvent.click(screen.getByRole('option', { name: option, exact: true }));
  await waitFor(() => expect(menu).not.toBeInTheDocument());
};
const add = async label => {
  await select(screen, 'Profil à ajouter', label);
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter une offre' }));
  return within(screen.getByRole('region', { name: label }));
};
const openProfiles = async () => {
  show();
  fireEvent.click(await screen.findByRole('tab', { name: 'Profils et offres' }));
};

beforeEach(() => {
  jest.clearAllMocks();
  institution = {
    nom: 'Établissement pilote',
    type: 'college',
    type_options: [{ value: 'college', label: 'Collège' }],
    configuration_academique: {
      language: 'fr', grading_scale: { minimum: 0, maximum: 100, pass_mark: 50 },
    },
    configuration_schema: { institutional_profiles: schema },
  };
  fetchApi.mockImplementation(async () => institution);
  patchApi.mockImplementation(async (_url, data) => {
    institution = { ...institution, ...data };
    return institution;
  });
});

it('saves four mixed profiles without changing existing grading rules or requiring credits everywhere', async () => {
  institution.configuration_schema.submission_window_types = [{ code: 'evaluation', label: 'Évaluation' }];
  await openProfiles();
  expect(screen.getByText('Aucune offre configurée. Le fonctionnement existant est conservé.')).toBeVisible();
  const primary = await add('École primaire');
  expect(primary.getByLabelText('Utiliser des crédits')).not.toBeChecked();
  fireEvent.change(primary.getByLabelText(/^Compétence reading/), { target: { value: 'Lire un texte' } });
  await add('Collège / lycée');
  const university = await add('Université / grande école');
  expect(university.getByLabelText('Utiliser des crédits')).toBeChecked();
  const vocational = await add('Formation professionnelle');
  expect(vocational.getByLabelText('Calendrier')).toHaveTextContent('Sessions courtes');
  fireEvent.submit(screen.getByRole('button', { name: 'Enregistrer la configuration' }).closest('form'));
  await waitFor(() => expect(patchApi).toHaveBeenCalledTimes(1));
  const saved = patchApi.mock.calls[0][1].configuration_academique;
  expect(saved.grading_scale).toEqual({ minimum: 0, maximum: 100, pass_mark: 50 });
  expect(saved.learning_offerings.map(offer => offer.profile)).toEqual([
    'primary', 'secondary', 'higher_education', 'vocational',
  ]);
  expect(saved.learning_offerings[0].assessment.criteria[0].label).toBe('Lire un texte');
  expect(saved.learning_offerings[0].credits).toBeNull();
  expect(saved.learning_offerings[2].credits.system).toBe('ECTS');
  expect(await screen.findByText('La configuration a été enregistrée.')).toBeVisible();
  expect(screen.getByRole('region', { name: 'École primaire' })).toBeVisible();
});

it('previews zero and missing scores separately and hides a stale simulation after editing its rules', async () => {
  postApi.mockResolvedValue({ status: 'failed', detail: 'Critères non satisfaits.' });
  await openProfiles();
  const secondary = await add('Collège / lycée');
  fireEvent.change(secondary.getByLabelText('Note à simuler'), { target: { value: '0' } });
  fireEvent.click(secondary.getByRole('button', { name: 'Simuler' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${endpoint}offering-preview/`, expect.objectContaining({ result: { score: '0' } })));
  expect(await secondary.findByText(/Critères non satisfaits/)).toBeVisible();
  fireEvent.change(secondary.getByLabelText(/^Seuil de réussite/), { target: { value: '12' } });
  expect(secondary.queryByText(/Critères non satisfaits/)).not.toBeInTheDocument();
  fireEvent.click(secondary.getByRole('button', { name: 'Simuler' }));
  await waitFor(() => expect(postApi).toHaveBeenLastCalledWith(`${endpoint}offering-preview/`, expect.objectContaining({ result: { score: null } })));
  expect(patchApi).not.toHaveBeenCalled();
});

it('previews explicit competency results and supports a custom pass/fail offer', async () => {
  postApi.mockResolvedValue({ status: 'passed', detail: 'Critères satisfaits.' });
  await openProfiles();
  const vocational = await add('Formation professionnelle');
  await select(vocational, 'Résultat : Lecture', 'Acquis / validé');
  fireEvent.click(vocational.getByRole('button', { name: 'Simuler' }));
  await waitFor(() => expect(postApi).toHaveBeenCalledWith(`${endpoint}offering-preview/`, expect.objectContaining({ result: { criteria: { reading: true } } })));
  const custom = await add('Profil personnalisé');
  await select(custom, 'Décision à simuler', 'Non acquis / non validé');
  fireEvent.click(custom.getByRole('button', { name: 'Simuler' }));
  await waitFor(() => expect(postApi).toHaveBeenLastCalledWith(`${endpoint}offering-preview/`, expect.objectContaining({ result: { passed: false } })));
});

it('surfaces server validation errors and keeps the unsaved offer available for correction', async () => {
  patchApi.mockRejectedValue({ response: { data: { configuration_academique: ['Barème invalide.'] } } });
  await openProfiles();
  const secondary = await add('Collège / lycée');
  fireEvent.change(secondary.getByLabelText(/^Seuil de réussite/), { target: { value: '30' } });
  fireEvent.submit(screen.getByRole('button', { name: 'Enregistrer la configuration' }).closest('form'));
  expect(await screen.findByText(/Barème invalide/)).toBeVisible();
  expect(secondary.getByLabelText(/^Seuil de réussite/)).toHaveValue(30);
});

it('treats a competency code matching an inherited property as unanswered until explicitly selected', async () => {
  institution.configuration_academique.learning_offerings = [{
    ...profiles[3].template,
    assessment: { mode: 'competency', criteria: [{ code: 'constructor', label: 'Lecture' }] },
  }];
  postApi.mockResolvedValue({ status: 'incomplete', detail: 'Toutes les compétences doivent être renseignées.' });
  await openProfiles();
  const vocational = within(screen.getByRole('region', { name: 'Formation professionnelle' }));
  fireEvent.click(vocational.getByRole('button', { name: 'Simuler' }));
  await waitFor(() => expect(postApi).toHaveBeenLastCalledWith(`${endpoint}offering-preview/`, expect.objectContaining({ result: { criteria: { constructor: null } } })));
  await select(vocational, 'Résultat : Lecture', 'Non acquis / non validé');
  fireEvent.click(vocational.getByRole('button', { name: 'Simuler' }));
  await waitFor(() => expect(postApi).toHaveBeenLastCalledWith(`${endpoint}offering-preview/`, expect.objectContaining({ result: { criteria: { constructor: false } } })));
});
