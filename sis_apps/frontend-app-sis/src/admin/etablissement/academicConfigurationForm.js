export const normalizeAcademicConfiguration = (value = {}) => ({
  ...value,
  dimensions: value.dimensions || [],
  permission_groups: value.permission_groups || [],
  validation_policies: value.validation_policies || [],
  financial_workflows: value.financial_workflows || [],
  import_templates: value.import_templates || [],
  exam_result_workflows: value.exam_result_workflows || [],
  reports: value.reports || [],
  submission_windows: value.submission_windows || {},
});

export const stringifyAcademicConfiguration = (value = {}) => JSON.stringify(
  normalizeAcademicConfiguration(value),
  null,
  2,
);

export const parseCsv = (value) => value.split(',').map((item) => item.trim()).filter(Boolean);
export const formatCsv = (value) => (Array.isArray(value) ? value.join(', ') : '');

export const parseObjectField = (value, label) => {
  if (!value.trim()) {
    return {};
  }
  const parsed = JSON.parse(value);
  if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
    throw new Error(`${label} doit être un objet JSON.`);
  }
  return parsed;
};

export const parseArrayField = (value, label) => {
  if (!value.trim()) {
    return [];
  }
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} doit être une liste JSON.`);
  }
  return parsed;
};
