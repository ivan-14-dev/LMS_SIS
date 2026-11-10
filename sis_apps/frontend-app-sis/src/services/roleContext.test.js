import {
  clearRoleContexts, getActiveRole, roleOptions, setActiveRole,
} from './roleContext';

afterEach(clearRoleContexts);

it('sends the selected role only to its own SIS API and preserves request options', () => {
  setActiveRole('https://sis.example/api/v1', 'parent');
  const options = { responseType: 'blob', headers: { 'X-CSRFToken': 'test-token' } };
  expect(roleOptions('https://sis.example/api/v1/portail/apprenant/', options)).toEqual({
    responseType: 'blob',
    headers: { 'X-CSRFToken': 'test-token', 'X-SIS-Role': 'parent' },
  });
  for (const url of ['https://other.example/api/v1/', 'https://sis.example/api/v10/', 'https://sis.example/external/']) {
    expect(roleOptions(url, options)).toBe(options);
  }
  setActiveRole('https://sis.example/api/v1', null);
  expect(getActiveRole('https://sis.example/api/v1/')).toBeNull();
  expect(roleOptions('https://sis.example/api/v1/portail/apprenant/', options)).toBe(options);
});
