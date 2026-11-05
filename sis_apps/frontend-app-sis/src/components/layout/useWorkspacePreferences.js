import { useEffect, useState } from 'react';

const defaults = { theme: 'light', favorites: [] };
const validate = (value) => {
  if (!value || !['light', 'dark'].includes(value.theme)
    || !Array.isArray(value.favorites) || value.favorites.some(item => typeof item !== 'string')
    || value.favorites.length > 100) {
    throw new SyntaxError('Préférences invalides.');
  }
  return { theme: value.theme, favorites: [...new Set(value.favorites)] };
};
const storageError = error => {
  if (!(error instanceof DOMException) && !(error instanceof SyntaxError)) { throw error; }
  return 'Les préférences de cet appareil ne peuvent pas être lues ou enregistrées. Les changements restent temporaires.';
};

export default function useWorkspacePreferences(scope) {
  const key = scope ? `sis.workspace.v1:${scope}` : null;
  const [state, setState] = useState({ key: null, value: defaults, error: '' });
  useEffect(() => {
    if (!key) { return undefined; }
    const load = () => {
      try {
        const saved = window.localStorage.getItem(key);
        setState({ key, value: saved ? validate(JSON.parse(saved)) : defaults, error: '' });
      } catch (error) {
        setState({ key, value: defaults, error: storageError(error) });
      }
    };
    load();
    const changed = event => { if (event.key === key || event.key === null) { load(); } };
    window.addEventListener('storage', changed);
    return () => window.removeEventListener('storage', changed);
  }, [key]);
  const current = state.key === key ? state : { value: defaults, error: '' };
  const update = changes => {
    if (!key || state.key !== key) { return; }
    const value = validate({ ...current.value, ...changes });
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
      setState({ key, value, error: '' });
    } catch (error) {
      setState({ key, value, error: storageError(error) });
    }
  };
  return {
    ...current.value, error: current.error, update, ready: Boolean(key && state.key === key),
  };
}
