import { fetchApi } from './api';
import {
  apiErrorMessage, downloadPdf, exportRecords, formatGrade,
} from './resources';

jest.mock('./api', () => ({ ...jest.requireActual('./api'), fetchApi: jest.fn() }));

it('fetches PDFs through the authenticated client and rejects HTML or failed downloads', async () => {
  const create = URL.createObjectURL;
  const revoke = URL.revokeObjectURL;
  const click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  URL.createObjectURL = jest.fn(() => 'blob:pdf-test');
  URL.revokeObjectURL = jest.fn();
  try {
    fetchApi.mockResolvedValue(new Blob(['%PDF-test'], { type: 'application/pdf' }));
    await downloadPdf('/authorized/pdf/', 'releve.pdf');
    expect(fetchApi).toHaveBeenCalledWith('/authorized/pdf/', { responseType: 'blob' });
    expect(click).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:pdf-test');
    fetchApi.mockResolvedValue(new Blob(['Connexion requise'], { type: 'text/html' }));
    await expect(downloadPdf('/authorized/pdf/', 'releve.pdf')).rejects.toThrow('PDF valide');
    const error = { response: { status: 403, data: new Blob(['Refusé']) } };
    fetchApi.mockRejectedValue(error);
    await expect(downloadPdf('/authorized/pdf/', 'releve.pdf')).rejects.toBe(error);
    expect(apiErrorMessage(error)).toContain('HTTP 403');
    expect(click).toHaveBeenCalledTimes(1);
  } finally {
    URL.createObjectURL = create;
    URL.revokeObjectURL = revoke;
    click.mockRestore();
  }
});

it('formats the actual scale, a real zero and non-numeric outcomes without inventing a grade', () => {
  expect(formatGrade({ valeur: '75.00', bareme: '100.00' })).toBe('75.00/100.00');
  expect(formatGrade({ valeur: 0, bareme: 20 })).toBe('0/20');
  expect(formatGrade({ valeur: null, resultat_offre: { detail: 'Critères satisfaits.' } })).toBe('Critères satisfaits.');
  expect(formatGrade({ valeur: null })).toBe('—');
});

it('exports nested offering and result labels and still escapes spreadsheet formulas', async () => {
  const create = URL.createObjectURL;
  const revoke = URL.revokeObjectURL;
  const click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  URL.createObjectURL = jest.fn(() => 'blob:export-test');
  URL.revokeObjectURL = jest.fn();
  try {
    exportRecords('Résultats', [
      { Header: 'Offre', accessor: 'offre_configuration.label' },
      { Header: 'Résultat', accessor: 'resultat_offre.detail' },
    ], [{ offre_configuration: { label: '=1+1' }, resultat_offre: { detail: 'Acquis' } }]);
    const blob = URL.createObjectURL.mock.calls[0][0];
    const text = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsText(blob);
    });
    expect(text).toContain('"\'=1+1","Acquis"');
  } finally {
    URL.createObjectURL = create;
    URL.revokeObjectURL = revoke;
    click.mockRestore();
  }
});
