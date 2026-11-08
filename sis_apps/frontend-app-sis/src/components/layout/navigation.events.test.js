import { canAccessModule, getNavigation, getWorkspaceGroups } from './navigation';

jest.mock('@mui/icons-material', () => new Proxy({ __esModule: true }, {
  get: (target, name) => (name === '__esModule' ? true : jest.requireActual(`@mui/icons-material/${name}`).default),
}));

it.each(['secondaire', 'superieur'])('routes managers and invited consultants to the enabled %s agenda without staff/role checks', variant => {
  ['core.gerer_evenement_institutionnel', 'core.consulter_evenement_institutionnel'].forEach(permission => {
    const capabilities = {
      role: 'parent', is_staff: false, permissions: [permission], modules: { 'sis.events': true },
    };
    const navigation = getNavigation(variant, variant, capabilities);
    const item = navigation.flatMap(section => section.items).find(link => link.path === `/${variant}/evenements`);
    expect(item.label).toBe('Événements institutionnels');
    expect(getWorkspaceGroups(navigation, 'learner').find(group => group.id === 'demarches').items).toContain(item);
    [undefined, {}, { 'sis.events': false }, { 'sis.events': 'true' }].forEach(modules => {
      const disabled = { ...capabilities, permissions: ['*'], modules };
      expect(canAccessModule(item, disabled)).toBe(false);
      expect(getNavigation(variant, variant, disabled).flatMap(section => section.items)).not.toContainEqual(item);
    });
    const roleOnly = {
      ...capabilities, role: 'direction', is_staff: true, permissions: [],
    };
    expect(canAccessModule(item, roleOnly)).toBe(false);
    expect(getNavigation(variant, variant, roleOnly).flatMap(section => section.items)).not.toContainEqual(item);
  });
});
