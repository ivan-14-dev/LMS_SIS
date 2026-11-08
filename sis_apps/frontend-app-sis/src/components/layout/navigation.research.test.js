import { getNavigation, getWorkspaceGroups } from './navigation';

jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));

const researchLinks = (variant, capabilities) => getNavigation(variant, variant, capabilities)
  .flatMap(section => section.items)
  .filter(item => item.path.endsWith('/recherche'));

it.each([
  'recherche.gerer_recherche',
  'recherche.consulter_recherche',
  'recherche.contribuer_recherche',
  'recherche.comptabiliser_recherche',
])('exposes university research with %s without requiring a staff role', permission => {
  const capabilities = {
    role: 'etudiant', is_staff: false, permissions: [permission], modules: { 'sis.research': true },
  };
  const [link] = researchLinks('superieur', capabilities);
  expect(link.path).toBe('/superieur/recherche');
  const groups = getWorkspaceGroups(getNavigation('superieur', 'superieur', capabilities), 'learner');
  expect(groups.flatMap(group => group.items)).toContainEqual(link);
  expect(researchLinks('secondaire', capabilities)).toEqual([]);
});

it.each([undefined, {}, { 'sis.research': false }, { 'sis.research': 'true' }])(
  'does not expose research with wildcard grants when activation is missing or invalid: %j',
  modules => {
    expect(researchLinks('superieur', { permissions: ['*'], modules })).toEqual([]);
  },
);

it('does not replace explicit research permissions with legacy roles or model-read grants', () => {
  [[], ['recherche.view_projetrecherche']].forEach(permissions => {
    expect(researchLinks('superieur', {
      role: 'chercheur', is_staff: true, permissions, modules: { 'sis.research': true },
    })).toEqual([]);
  });
});
