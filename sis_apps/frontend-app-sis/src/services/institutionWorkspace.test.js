import { accountsLinked, institutionNavigation } from './institutionWorkspace';
import { getWorkspaceGroups } from '../components/layout/navigation';

const pair = () => {
  const left = {
    workspace: {
      id: 'a',
      peer: 'b',
      home: 'a',
      variant: 'secondaire',
      variants: ['secondaire', 'superieur'],
      name: 'Institution',
      user: 1,
      version: 'v1',
      account_link: { peer: 'b', user: 2, version: 'v1' },
    },
    permissions: ['*'],
    role: 'direction',
  };
  const right = {
    workspace: {
      id: 'b',
      peer: 'a',
      home: 'a',
      variant: 'superieur',
      variants: ['superieur'],
      user: 2,
      version: 'v2',
      account_link: { peer: 'a', user: 1, version: 'v2' },
    },
    permissions: ['*'],
    role: 'president',
    modules: { 'sis.research': true },
  };
  return [left, right];
};

it('unites real module routes without losing duplicate services or administrative contexts', () => {
  const [left, right] = pair();
  const result = institutionNavigation('secondaire', left, right, '');
  expect(result.unified).toBe(true);
  const items = getWorkspaceGroups(result.sections, 'administration').flatMap(group => group.items);
  expect(items.map(item => item.path)).toEqual(expect.arrayContaining([
    '/secondaire/classes', '/superieur/formations', '/secondaire/cantine',
    '/superieur/recherche', '/secondaire/examens', '/superieur/examens',
    '/admin/utilisateurs?sis=secondaire', '/admin/utilisateurs?sis=superieur',
  ]));
  expect(items.filter(item => item.path.endsWith('/examens')).map(item => item.label))
    .toEqual(['Examens · Secondaire', 'Examens · Supérieur']);
  expect(institutionNavigation('superieur', right, left, '').sections).toEqual(result.sections);
});

it('applies each source permissions and denials instead of borrowing the other account privileges', () => {
  const [left, right] = pair();
  right.permissions = ['formations.view_formation'];
  right.denied_permissions = ['formations.view_formation'];
  const items = institutionNavigation('secondaire', left, right, '').sections.flatMap(section => section.items);
  expect(items.some(item => item.path === '/secondaire/classes')).toBe(true);
  expect(items.some(item => item.path === '/superieur/formations')).toBe(false);
  expect(items.some(item => item.path === '/superieur/etudiants')).toBe(false);
});

it.each(['institution', 'identity', 'revision', 'home'])('fails closed for mismatched %s declarations', (mismatch) => {
  const [left, right] = pair();
  if (mismatch === 'institution') { right.workspace.peer = 'unrelated'; }
  if (mismatch === 'identity') { right.workspace.user = 99; }
  if (mismatch === 'revision') { right.workspace.version = 'new-revision'; }
  if (mismatch === 'home') { right.workspace.home = 'b'; }
  expect(accountsLinked(left.workspace, right.workspace)).toBe(false);
  const result = institutionNavigation('secondaire', left, right, '');
  expect(result.unified).toBe(false);
  expect(result.sections.flatMap(section => section.items).some(item => item.path.startsWith('/superieur'))).toBe(false);
});

it('uses the institutional type selected at the seat while retaining seat administration', () => {
  const [left, right] = pair();
  left.workspace.variants = ['superieur'];
  const result = institutionNavigation('secondaire', left, right, '');
  const paths = result.sections.flatMap(section => section.items).map(item => item.path);
  expect(paths).toContain('/superieur/formations');
  expect(paths).not.toContain('/secondaire/classes');
  expect(paths).toContain('/admin/etablissement?sis=secondaire');
  expect(paths).toContain('/secondaire');
});

it('keeps only the seat institution settings even when the higher-education engine is the seat', () => {
  const [left, right] = pair();
  left.workspace.home = 'b';
  right.workspace.home = 'b';
  right.workspace.variants = ['secondaire', 'superieur'];
  const paths = institutionNavigation('secondaire', left, right, '')
    .sections.flatMap(section => section.items).map(item => item.path);
  expect(paths.filter(path => path.startsWith('/admin/etablissement?')))
    .toEqual(['/admin/etablissement?sis=superieur']);
});
