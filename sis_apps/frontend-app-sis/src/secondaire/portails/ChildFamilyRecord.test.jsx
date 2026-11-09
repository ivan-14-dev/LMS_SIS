/* eslint-disable react/prop-types -- lightweight records-tab rendering stub */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../../services/api';
import { downloadPdf } from '../../services/resources';
import ChildFamilyRecord from './ChildFamilyRecord';

jest.mock('@tanstack/react-query', () => ({ useQuery: jest.fn() }));
jest.mock('../../services/api', () => ({
  getSecondaireApiUrl: () => 'https://sis.test/api/v1', fetchApi: jest.fn(),
}));
jest.mock('../../services/resources', () => ({
  downloadPdf: jest.fn(), apiErrorMessage: error => error?.message || '',
}));
jest.mock('../../components/common', () => ({
  SISDataTable: function Table() { return <div>Table</div>; },
}));
jest.mock('../../components/common/RecordsTabs', () => function Panels({ panels }) {
  return panels.map(panel => <section key={panel.label}>{panel.content}</section>);
});

const pupils = [{ id: 4, nom: 'Enfant A' }, { id: 5, nom: 'Enfant B' }];
const record = {
  enfant: { id: 4, nom: 'Enfant A' }, notes: [], absences: [], planning: [], factures: [],
  bulletins: [{ id: 9, periode: 'Trimestre 1', classe: '6e A', moyenne: 15 }],
};
const selectChild = () => {
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Consulter le dossier d’un enfant' }));
  fireEvent.click(screen.getByRole('option', { name: 'Enfant A' }));
};
let refetch;

beforeEach(() => {
  jest.clearAllMocks();
  refetch = jest.fn();
  useQuery.mockReturnValue({ data: record, refetch });
  downloadPdf.mockResolvedValue(undefined);
});

it('loads only the selected child and uses authenticated private PDF download', async () => {
  render(<ChildFamilyRecord pupils={pupils} />);
  expect(useQuery).not.toHaveBeenCalled();
  selectChild();
  const options = useQuery.mock.calls[0][0];
  expect(options).toEqual(expect.objectContaining({
    queryKey: ['family-child-record', 4], refetchOnMount: 'always', refetchOnWindowFocus: 'always',
  }));
  await options.queryFn();
  expect(fetchApi).toHaveBeenCalledWith('https://sis.test/api/v1/portail/apprenant/dossier_enfant/?enfant_id=4');
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le bulletin 9' }));
  await waitFor(() => expect(downloadPdf).toHaveBeenCalledWith('https://sis.test/api/v1/bulletins/9/pdf_officiel/', 'bulletin-9.pdf'));
});

it('unmounts the selected child when the refreshed affiliation list removes it', () => {
  const { rerender } = render(<ChildFamilyRecord pupils={pupils} />);
  selectChild();
  expect(screen.getByRole('heading', { name: 'Enfant A' })).toBeVisible();
  rerender(<ChildFamilyRecord pupils={[pupils[1]]} />);
  expect(screen.queryByRole('heading', { name: 'Enfant A' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Télécharger le bulletin 9' })).not.toBeInTheDocument();
});

it.each([
  { isFetching: true },
  { error: new Error('Liaison retirée') },
])('never renders cached records during revalidation or after refusal: %j', (state) => {
  useQuery.mockReturnValue({ data: record, refetch, ...state });
  render(<ChildFamilyRecord pupils={pupils} />);
  selectChild();
  expect(screen.queryByRole('heading', { name: 'Enfant A' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Télécharger le bulletin 9' })).not.toBeInTheDocument();
});

it('revalidates the dossier after an independently refused PDF download', async () => {
  downloadPdf.mockRejectedValue(new Error('Téléchargement refusé'));
  render(<ChildFamilyRecord pupils={pupils} />);
  selectChild();
  fireEvent.click(screen.getByRole('button', { name: 'Télécharger le bulletin 9' }));
  await screen.findByText('Téléchargement refusé');
  expect(refetch).toHaveBeenCalled();
});
