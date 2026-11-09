import { getNavigation, getWorkspaceGroups } from './navigation';
import { practicalPermissions } from '../../practical/practicalContract';

jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));
const links = (variant, caps) => getNavigation(variant, variant, caps).flatMap(section => section.items)
  .filter(item => item.path.endsWith('/stages-pratiques'));

it.each(['secondaire', 'superieur'])('exposes practical work in %s with named grants, never a role/contact-derived grant', variant => {
  practicalPermissions.forEach(permission => {
    const caps = {
      role: 'etudiant', is_staff: false, contact_entreprise: 3, permissions: [permission], modules: { 'sis.practical_training': true },
    };
    const [link] = links(variant, caps);
    expect(link.path).toBe(`/${variant}/stages-pratiques`);
    expect(getWorkspaceGroups(getNavigation(variant, variant, caps), 'learner').flatMap(group => group.items)).toContainEqual(link);
  });
  expect(links(variant, {
    role: 'direction', is_staff: true, permissions: [], modules: { 'sis.practical_training': true },
  })).toEqual([]);
});
it.each([undefined, {}, { 'sis.practical_training': false }, { 'sis.practical_training': 'true' }])(
  'keeps practical training disabled by default even with wildcard permissions: %j',
  modules => {
    ['secondaire', 'superieur'].forEach(variant => expect(links(variant, { permissions: ['*'], modules })).toEqual([]));
  },
);
it('leaves the legacy upper stage navigation in its distinct scope', () => {
  const items = getNavigation('superieur', 'superieur', {
    permissions: ['stages.view_conventionstage'], modules: { 'sis.practical_training': false },
  }).flatMap(section => section.items);
  expect(items.some(item => item.path === '/superieur/stages')).toBe(true);
  expect(items.some(item => item.path === '/superieur/stages-pratiques')).toBe(false);
});
