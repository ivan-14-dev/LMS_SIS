import { act, renderHook } from '@testing-library/react';
import useWorkspacePreferences from './useWorkspacePreferences';

beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { jest.restoreAllMocks(); });

it('isolates preferences per account and tenant, and reloads them without persisting personal dossier data', () => {
  const { result, rerender, unmount } = renderHook(({ scope }) => useWorkspacePreferences(scope), {
    initialProps: { scope: 'tenant-a:account-1' },
  });
  act(() => result.current.update({ theme: 'dark', favorites: ['/secondaire/classes'] }));
  rerender({ scope: 'tenant-a:account-2' });
  expect(result.current.theme).toBe('light');
  expect(result.current.favorites).toEqual([]);
  rerender({ scope: 'tenant-b:account-1' });
  expect(result.current.favorites).toEqual([]);
  rerender({ scope: 'tenant-a:account-1' });
  expect(result.current.theme).toBe('dark');
  expect(result.current.favorites).toEqual(['/secondaire/classes']);
  unmount();
  const restored = renderHook(() => useWorkspacePreferences('tenant-a:account-1'));
  expect(restored.result.current.theme).toBe('dark');
  expect(Object.keys(JSON.parse(window.localStorage.getItem('sis.workspace.v1:tenant-a:account-1'))))
    .toEqual(['theme', 'favorites']);
});

it('warns about malformed or unavailable storage instead of claiming persistent success', () => {
  window.localStorage.setItem('sis.workspace.v1:test', 'malformed');
  const { result } = renderHook(() => useWorkspacePreferences('test'));
  expect(result.current.error).toContain('temporaires');
  const save = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Denied'); });
  act(() => result.current.update({ theme: 'dark' }));
  expect(result.current.theme).toBe('dark');
  expect(result.current.error).toContain('temporaires');
  save.mockRestore();
  act(() => result.current.update({ theme: 'light' }));
  expect(result.current.error).toBe('');
});

it('observes changes from another tab and does not save before the account is known', () => {
  const options = { initialProps: { scope: null } };
  const { result, rerender } = renderHook(({ scope }) => useWorkspacePreferences(scope), options);
  act(() => result.current.update({ theme: 'dark' }));
  expect(window.localStorage.length).toBe(0);
  rerender({ scope: 'test' });
  window.localStorage.setItem('sis.workspace.v1:test', JSON.stringify({ theme: 'dark', favorites: [] }));
  act(() => window.dispatchEvent(new StorageEvent('storage', { key: 'sis.workspace.v1:test' })));
  expect(result.current.theme).toBe('dark');
});
