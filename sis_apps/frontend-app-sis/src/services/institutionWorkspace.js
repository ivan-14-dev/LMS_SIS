import { getNavigation } from '../components/layout/navigation';

export const otherVariant = variant => (variant === 'secondaire' ? 'superieur' : 'secondaire');

export const institutionsLinked = (left, right) => Boolean(left && right
  && left.variant !== right.variant && left.peer === right.id && right.peer === left.id
  && left.home === right.home && [left.id, right.id].includes(left.home));

export const accountsLinked = (left, right) => institutionsLinked(left, right)
  && left.account_link?.peer === right.id && left.account_link?.user === right.user
  && right.account_link?.peer === left.id && right.account_link?.user === left.user
  && left.account_link?.version === left.version && right.account_link?.version === right.version;

export const institutionNavigation = (variant, current, peer, search) => {
  const local = getNavigation(variant, variant, current, search);
  if (!accountsLinked(current?.workspace, peer?.workspace)) {
    return { sections: local, unified: false };
  }
  const capabilities = { [variant]: current, [otherVariant(variant)]: peer };
  const home = [current.workspace, peer.workspace].find(workspace => workspace.id === current.workspace.home);
  const sections = [];
  home.variants.forEach((source) => {
    getNavigation(source, source, capabilities[source], search).forEach((section) => {
      let destination = sections.find(item => item.title === section.title);
      if (!destination) {
        destination = { ...section, items: [] };
        sections.push(destination);
      }
      destination.items.push(...section.items
        .filter(item => !item.end || source === home.variant)
        .filter(item => !item.path.startsWith('/admin/etablissement?') || source === home.variant)
        .map(item => ({ ...item, source })));
    });
    if (!home.variants.includes(home.variant)) {
      const homeSections = getNavigation(home.variant, home.variant, capabilities[home.variant], search);
      sections.unshift({
        title: 'Siège',
        items: homeSections.flatMap(section => section.items)
          .filter(item => item.end || item.path.startsWith('/admin/etablissement?'))
          .map(item => ({ ...item, source: home.variant })),
      });
    }
  });
  const labelledSections = sections.map(section => {
    const counts = section.items.reduce((all, item) => ({ ...all, [item.label]: (all[item.label] || 0) + 1 }), {});
    return {
      ...section,
      items: section.items.map(item => ({
        ...item,
        label: counts[item.label] > 1 ? `${item.label} · ${item.source === 'secondaire' ? 'Secondaire' : 'Supérieur'}` : item.label,
      })),
    };
  });
  return { sections: labelledSections, unified: true, home };
};
