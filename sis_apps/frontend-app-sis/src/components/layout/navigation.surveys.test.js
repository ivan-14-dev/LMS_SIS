import { canAccessModule, getNavigation, getWorkspaceGroups } from './navigation';

jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));

it.each(['secondaire', 'superieur'])('exposes an explicit recipient portal in %s without a management grant', variant => {
  const capabilities = { role: 'parent', permissions: [], modules: { 'sis.surveys': true } };
  const navigation = getNavigation(variant, variant, capabilities);
  const item = navigation.flatMap(section => section.items).find(link => link.path === `/${variant}/portail-enquetes`);
  expect(item).toMatchObject({ label: 'Mes enquêtes institutionnelles', public: true, module: 'sis.surveys' });
  expect(getWorkspaceGroups(navigation, 'learner').find(group => group.id === 'demarches').items).toContain(item);
  [undefined, {}, { 'sis.surveys': false }, { 'sis.surveys': 'true' }].forEach(modules => {
    const disabled = { ...capabilities, permissions: ['*'], modules };
    expect(canAccessModule(item, disabled)).toBe(false);
    expect(getNavigation(variant, variant, disabled).flatMap(section => section.items)).not.toContainEqual(item);
  });
});
