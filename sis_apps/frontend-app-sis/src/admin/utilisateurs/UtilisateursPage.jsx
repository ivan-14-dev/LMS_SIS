import React, { useState } from 'react';
import {
  Alert, Box, Tab, Tabs, Typography,
} from '@mui/material';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import ResourceManager from '../../components/common/ResourceManager';
import { getEnabledVariants } from '../../services/resources';
import InstitutionalGroupsEditor from './InstitutionalGroupsEditor';

const UtilisateursPage = () => {
  const [params] = useSearchParams();
  const { capabilities, loading, error } = useOutletContext() || {};
  const [tab, setTab] = useState(null);
  const variants = getEnabledVariants();
  const variant = variants.includes(params.get('sis')) ? params.get('sis') : variants[0];
  const can = permission => capabilities?.permissions?.includes('*')
    || capabilities?.permissions?.includes(permission);
  const canViewAccounts = can('utilisateurs.view_utilisateur');
  const activeTab = tab || (can('auth.view_group') && !canViewAccounts ? 'groupes' : 'comptes');
  const roles = variant === 'secondaire'
    ? ['direction', 'responsable_pedagogique', 'enseignant', 'personnel_administratif', 'comptable',
      'bibliothecaire', 'infirmier', 'surveillant', 'vie_scolaire', 'eleve', 'parent']
    : ['president', 'vice_president', 'doyen', 'directeur_dept', 'responsable_formation',
      'directeur_etudes', 'enseignant', 'chercheur', 'personnel_administratif', 'scolarite',
      'service_social', 'service_ri', 'bibliothecaire', 'comptable', 'etudiant', 'doctorant', 'parent'];
  if (loading || (!capabilities && !error)) {
    return <Typography role="status">Chargement des autorisations…</Typography>;
  }
  if (error) { return <Alert severity="error">Impossible de vérifier les autorisations de cette page.</Alert>; }
  let content;
  if (activeTab === 'groupes') {
    content = <InstitutionalGroupsEditor variant={variant} capabilities={capabilities} />;
  } else {
    content = (
      <ResourceManager
        key={variant}
        variant={variant}
        resource="utilisateurs/comptes"
        title="Utilisateurs"
        showHeading={false}
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
            name: 'role', label: 'Rôle', required: true, choices: roles.map(value => ({ value, label: value })),
          },
        ]}
        actions={[{ label: 'Déconnecter les sessions', endpoint: 'force_logout' }]}
      />
    );
  }
  return (
    <Box>
      <Typography component="h1" variant="h4" sx={{ mb: 2 }}>Utilisateurs</Typography>
      <Tabs value={activeTab} onChange={(_event, value) => setTab(value)} aria-label="Administration des utilisateurs" sx={{ mb: 3 }}>
        <Tab value="comptes" label="Comptes" />
        <Tab value="groupes" label="Groupes et permissions" />
      </Tabs>
      {content}
    </Box>
  );
};

export default UtilisateursPage;
