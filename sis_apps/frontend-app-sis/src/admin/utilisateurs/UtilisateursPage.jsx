import React, { useState } from 'react';
import {
  Alert, Box, Tab, Tabs, Typography,
} from '@mui/material';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import ResourceManager from '../../components/common/ResourceManager';
import { getEnabledVariants } from '../../services/resources';
import InstitutionalGroupsEditor from './InstitutionalGroupsEditor';
import GuardianLinksEditor from './GuardianLinksEditor';
import AccountAccessEditor from './AccountAccessEditor';

const UtilisateursPage = () => {
  const [params] = useSearchParams();
  const { capabilities, loading, error } = useOutletContext() || {};
  const [tab, setTab] = useState(null);
  const variants = getEnabledVariants();
  const variant = variants.includes(params.get('sis')) ? params.get('sis') : variants[0];
  const can = permission => capabilities?.permissions?.includes('*')
    || capabilities?.permissions?.includes(permission);
  const canViewAccounts = can('utilisateurs.view_utilisateur');
  const canViewGroups = can('auth.view_group');
  const canManageAccess = canViewAccounts && canViewGroups
    && can('utilisateurs.change_utilisateur') && can('auth.change_group');
  const canViewParents = variant === 'secondaire' && (can('eleves.view_tuteur') || can('eleves.view_elevetuteur'));
  let defaultTab = 'comptes';
  if (!canViewAccounts && canViewGroups) { defaultTab = 'groupes'; }
  if (!canViewAccounts && !canViewGroups && canViewParents) { defaultTab = 'parents'; }
  const allowedTabs = {
    comptes: canViewAccounts, groupes: canViewGroups, parents: canViewParents, acces: canManageAccess,
  };
  const activeTab = allowedTabs[tab] ? tab : defaultTab;
  const roles = variant === 'secondaire'
    ? ['direction', 'responsable_pedagogique', 'enseignant', 'personnel_administratif', 'comptable',
      'bibliothecaire', 'infirmier', 'surveillant', 'vie_scolaire', 'eleve', 'parent', 'partenaire']
    : ['president', 'vice_president', 'doyen', 'directeur_dept', 'responsable_formation',
      'directeur_etudes', 'enseignant', 'chercheur', 'personnel_administratif', 'scolarite',
      'service_social', 'service_ri', 'bibliothecaire', 'comptable', 'etudiant', 'doctorant', 'parent', 'partenaire'];
  if (loading || (!capabilities && !error)) {
    return <Typography role="status">Chargement des autorisations…</Typography>;
  }
  if (error) { return <Alert severity="error">Impossible de vérifier les autorisations de cette page.</Alert>; }
  if (!canViewAccounts && !canViewGroups && !canViewParents) {
    return <Alert severity="warning">Vous n’avez pas les autorisations de consultation de cette page.</Alert>;
  }
  let content;
  if (activeTab === 'acces') {
    content = <AccountAccessEditor key={variant} variant={variant} />;
  } else if (activeTab === 'groupes') {
    content = <InstitutionalGroupsEditor variant={variant} capabilities={capabilities} />;
  } else if (activeTab === 'parents' && variant === 'secondaire') {
    content = <GuardianLinksEditor capabilities={capabilities} />;
  } else {
    content = (
      <ResourceManager
        key={variant}
        variant={variant}
        resource="utilisateurs/comptes"
        title="Utilisateurs"
        showHeading={false}
        allowCreate={can('utilisateurs.add_utilisateur')}
        allowEdit={can('utilisateurs.change_utilisateur')}
        columns={[
          { Header: 'Identifiant', accessor: 'username' },
          { Header: 'Nom complet', accessor: 'full_name' },
          { Header: 'Email', accessor: 'email' },
          { Header: 'Rôle', accessor: 'role_display' },
          { Header: 'Actif', accessor: 'is_active', Cell: ({ value }) => (value ? 'Oui' : 'Non') },
        ]}
        fields={[
          {
            name: 'username', label: 'Identifiant', required: true, createOnly: true,
          },
          { name: 'first_name', label: 'Prénom', required: true },
          { name: 'last_name', label: 'Nom', required: true },
          {
            name: 'email', label: 'Email', type: 'email', required: true,
          },
          {
            name: 'password', label: 'Mot de passe initial', type: 'password', required: true, createOnly: true,
          },
          {
            name: 'password_confirm', label: 'Confirmation du mot de passe', type: 'password', required: true, createOnly: true,
          },
          {
            name: 'role',
            label: 'Rôle',
            required: true,
            choices: roles.map(value => ({ value, label: value === 'partenaire' ? 'Partenaire' : value })),
          },
        ]}
        actions={can('utilisateurs.change_utilisateur') ? [{ label: 'Déconnecter les sessions', endpoint: 'force_logout' }] : []}
      />
    );
  }
  return (
    <Box>
      <Typography component="h1" variant="h4" sx={{ mb: 2 }}>Utilisateurs</Typography>
      <Tabs value={activeTab} onChange={(_event, value) => setTab(value)} aria-label="Administration des utilisateurs" sx={{ mb: 3 }}>
        <Tab value="comptes" label="Comptes" disabled={!canViewAccounts} />
        <Tab value="groupes" label="Groupes et permissions" disabled={!canViewGroups} />
        {canManageAccess && <Tab value="acces" label="Rôles et accès individuels" />}
        {canViewParents && (
          <Tab value="parents" label="Parents et enfants" />
        )}
      </Tabs>
      {content}
    </Box>
  );
};

export default UtilisateursPage;
