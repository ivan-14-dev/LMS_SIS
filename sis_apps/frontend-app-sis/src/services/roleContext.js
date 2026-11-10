const roles = new Map();
const absolute = url => new URL(url, window.location.origin).href;

export const getActiveRole = (url) => {
  const target = absolute(url);
  return [...roles].find(([base]) => `${target.replace(/\/$/, '')}/`.startsWith(base))?.[1] || null;
};

export const setActiveRole = (baseUrl, role) => {
  const base = `${absolute(baseUrl).replace(/\/$/, '')}/`;
  if (role) { roles.set(base, role); } else { roles.delete(base); }
};

export const clearRoleContexts = () => roles.clear();

export const roleOptions = (url, options = {}) => {
  const role = getActiveRole(url);
  return role ? { ...options, headers: { ...options.headers, 'X-SIS-Role': role } } : options;
};
