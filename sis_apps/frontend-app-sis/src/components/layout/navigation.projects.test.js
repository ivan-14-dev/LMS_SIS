import { canAccessModule, getNavigation, getWorkspaceGroups } from './navigation';

jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));

it.each(['secondaire', 'superieur'])('closes projects by default in %s without changing legacy modules', variant => {
  [undefined, {}, { 'sis.projects': false }, { 'sis.projects': 'true' }].forEach(modules => {
    const capabilities = { permissions: ['*'], modules };
    const items = getNavigation(variant, variant, capabilities).flatMap(section => section.items);
    expect(items.some(item => item.path === `/${variant}/projets`)).toBe(false);
    expect(canAccessModule({ public: true, module: 'sis.projects' }, capabilities)).toBe(false);
    expect(canAccessModule({ public: true, module: 'sis.delegations' }, capabilities)).toBe(true);
  });
});

it.each([
  ['secondaire', 'eleve', 'learner', 'Mes projets', 'demarches'],
  ['superieur', 'etudiant', 'learner', 'Mes projets', 'demarches'],
  ['secondaire', 'enseignant', 'teacher', 'Projets pédagogiques', 'pedagogie'],
  ['superieur', 'enseignant', 'teacher', 'Projets pédagogiques', 'pedagogie'],
])('exposes scoped projects for %s / %s', (variant, role, kind, label, groupId) => {
  const capabilities = { role, permissions: [], modules: { 'sis.projects': true } };
  const navigation = getNavigation(variant, variant, capabilities);
  const item = navigation.flatMap(section => section.items).find(link => link.path === `/${variant}/projets`);
  expect(item).toMatchObject({ label, public: true });
  expect(item.permission).toBeUndefined();
  expect(getWorkspaceGroups(navigation, kind).find(group => group.id === groupId).items).toContain(item);
  const disabled = getNavigation(variant, variant, { ...capabilities, modules: {} });
  expect(disabled.flatMap(section => section.items)).not.toContainEqual(item);
});
