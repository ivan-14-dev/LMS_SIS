import React from 'react';
import { render, screen } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';

import PermissionGuard from './PermissionGuard';

jest.mock('@tanstack/react-query', () => ({
  useQuery: jest.fn(),
}));

describe('PermissionGuard', () => {
  it('renders children when the backend grants the permission', () => {
    useQuery.mockReturnValue({
      data: { permissions: ['notes.view_note'], role: 'custom_role' },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard type="superieur" permission="notes.view_note">
        <div>Notes</div>
      </PermissionGuard>,
    );

    expect(screen.getByText('Notes')).toBeInTheDocument();
  });

  it('does not use a legacy role to bypass a revoked permission', () => {
    useQuery.mockReturnValue({
      data: { permissions: [], role: 'enseignant' },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard
        type="secondaire"
        permission="notes.view_evaluation"
        allowedRoles={['enseignant']}
      >
        <div>Évaluations</div>
      </PermissionGuard>,
    );

    expect(screen.queryByText('Évaluations')).not.toBeInTheDocument();
    expect(screen.getByText(/permission/)).toBeInTheDocument();
  });

  it('supports additional group checks', () => {
    useQuery.mockReturnValue({
      data: { permissions: ['notes.view_note'], role: 'custom_role', groups: ['finance'] },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard
        type="superieur"
        permission="notes.view_note"
        allowedGroups={['finance']}
      >
        <div>Finance</div>
      </PermissionGuard>,
    );

    expect(screen.getByText('Finance')).toBeInTheDocument();
  });

  it('supports nested attribute checks', () => {
    useQuery.mockReturnValue({
      data: {
        permissions: ['notes.view_note'],
        role: 'custom_role',
        attributes: { domains: ['finance'], visibility: { campus: 'centre' } },
      },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard
        type="superieur"
        permission="notes.view_note"
        requiredAttributes={{ domains: ['finance'], 'visibility.campus': 'centre' }}
      >
        <div>Vue filtrée</div>
      </PermissionGuard>,
    );

    expect(screen.getByText('Vue filtrée')).toBeInTheDocument();
  });

  it('denies access without a permission or compatible role', () => {
    useQuery.mockReturnValue({
      data: { permissions: [], role: 'visiteur' },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard type="superieur" permission="notes.view_note">
        <div>Notes</div>
      </PermissionGuard>,
    );

    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.getByText(/permission/)).toBeInTheDocument();
  });

  it('denies access when a required attribute is missing', () => {
    useQuery.mockReturnValue({
      data: {
        permissions: ['notes.view_note'],
        role: 'custom_role',
        attributes: { visibility: { campus: 'nord' } },
      },
      isLoading: false,
      isError: false,
    });

    render(
      <PermissionGuard
        type="superieur"
        permission="notes.view_note"
        requiredAttributes={{ 'visibility.campus': 'centre' }}
      >
        <div>Notes</div>
      </PermissionGuard>,
    );

    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
    expect(screen.getByText(/permission/)).toBeInTheDocument();
  });

  it.each(['secondaire', 'superieur'])('requires an active affiliation and effective grant for %s staff links', (type) => {
    const data = {
      role: 'enseignant', permissions: ['portail.view_staff'], affiliations: [{ kind: 'staff', active: true }],
    };
    useQuery.mockReturnValue({ data, isLoading: false, isError: false });
    const { rerender } = render(
      <PermissionGuard type={type} portal="staff"><div>Activité staff</div></PermissionGuard>,
    );
    expect(screen.getByText('Activité staff')).toBeInTheDocument();
    useQuery.mockReturnValue({ data: { ...data, permissions: [] }, isLoading: false, isError: false });
    rerender(<PermissionGuard type={type} portal="staff"><div>Activité staff</div></PermissionGuard>);
    expect(screen.queryByText('Activité staff')).not.toBeInTheDocument();
    useQuery.mockReturnValue({
      data: { ...data, affiliations: [{ kind: 'staff', active: false }] }, isLoading: false, isError: false,
    });
    rerender(<PermissionGuard type={type} portal="staff"><div>Activité staff</div></PermissionGuard>);
    expect(screen.queryByText('Activité staff')).not.toBeInTheDocument();
  });

  it('does not display cached portal content while rechecking capabilities or after an error', () => {
    const data = {
      permissions: ['portail.view_learner'], affiliations: [{ kind: 'learner', active: true }],
    };
    useQuery.mockReturnValue({ data, isLoading: false, isFetching: true });
    const { rerender } = render(
      <PermissionGuard type="superieur" portal="learner"><div>Dossier</div></PermissionGuard>,
    );
    expect(screen.queryByText('Dossier')).not.toBeInTheDocument();
    useQuery.mockReturnValue({ data, isLoading: false, isError: true });
    rerender(<PermissionGuard type="superieur" portal="learner"><div>Dossier</div></PermissionGuard>);
    expect(screen.queryByText('Dossier')).not.toBeInTheDocument();
    expect(screen.getByText(/Impossible de vérifier/)).toBeInTheDocument();
  });

  it('keeps parent access distinct from learner access', () => {
    useQuery.mockReturnValue({
      data: { portals: { parent: true }, affiliations: [{ kind: 'parent', active: true }] },
      isLoading: false,
    });
    render(
      <PermissionGuard type="secondaire" portal={['learner', 'parent']}><div>Famille</div></PermissionGuard>,
    );
    expect(screen.getByText('Famille')).toBeInTheDocument();
  });

  it('honors an explicit portal revocation even when the user has wildcard permissions', () => {
    useQuery.mockReturnValue({
      data: {
        permissions: ['*'], portals: { staff: false }, affiliations: [{ kind: 'staff', active: true }],
      },
      isLoading: false,
    });
    render(
      <PermissionGuard type="secondaire" portal="staff"><div>Administration</div></PermissionGuard>,
    );
    expect(screen.queryByText('Administration')).not.toBeInTheDocument();
    expect(screen.getByText(/affiliation actuelle/)).toBeInTheDocument();
  });
});
