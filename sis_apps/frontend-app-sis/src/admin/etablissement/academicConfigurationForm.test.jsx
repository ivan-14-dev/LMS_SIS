import {
  formatCsv,
  normalizeAcademicConfiguration,
  parseArrayField,
  parseCsv,
  parseObjectField,
  stringifyAcademicConfiguration,
} from './academicConfigurationForm';

describe('academicConfigurationForm helpers', () => {
  it('normalizes missing dynamic sections for structured editing', () => {
    expect(normalizeAcademicConfiguration({ grading_scale: { pass_mark: 10 } })).toEqual({
      grading_scale: { pass_mark: 10 },
      dimensions: [],
      permission_groups: [],
      validation_policies: [],
      financial_workflows: [],
      import_templates: [],
      exam_result_workflows: [],
      reports: [],
    });
  });

  it('keeps string and object representations synchronized', () => {
    const configuration = {
      dimensions: [{ code: 'campus', label: 'Campus' }],
      reports: [{ code: 'payments', label: 'Paiements', fields: ['numero'] }],
    };

    const json = stringifyAcademicConfiguration(configuration);
    const parsed = normalizeAcademicConfiguration(JSON.parse(json));

    expect(json).toContain('"code": "campus"');
    expect(parsed).toEqual({
      dimensions: [{ code: 'campus', label: 'Campus' }],
      reports: [{ code: 'payments', label: 'Paiements', fields: ['numero'] }],
      permission_groups: [],
      validation_policies: [],
      financial_workflows: [],
      import_templates: [],
      exam_result_workflows: [],
    });
  });

  it('parses CSV and JSON helper fields used by the structured editors', () => {
    expect(parseCsv('notes.view_note, paiements.change_paiement')).toEqual([
      'notes.view_note',
      'paiements.change_paiement',
    ]);
    expect(formatCsv(['annee', 'classe'])).toBe('annee, classe');
    expect(parseObjectField('{"niveau":"L1"}', 'Targets')).toEqual({ niveau: 'L1' });
    expect(parseArrayField('[{"code":"draft"}]', 'Étapes')).toEqual([{ code: 'draft' }]);
  });
});
