import React from 'react';
import { useSearchParams } from 'react-router-dom';
import ResourceManager from '../../components/common/ResourceManager';
import { getEnabledVariants } from '../../services/resources';

const UtilisateursPage = () => {
  const [params] = useSearchParams();
  const variants = getEnabledVariants();
  const variant = variants.includes(params.get('sis')) ? params.get('sis') : variants[0];
  const roles = variant === 'secondaire'
    ? ['direction', 'responsable_pedagogique', 'enseignant', 'personnel_administratif', 'comptable',
      'bibliothecaire', 'infirmier', 'surveillant', 'vie_scolaire', 'eleve', 'parent']
    : ['president', 'vice_president', 'doyen', 'directeur_dept', 'responsable_formation',
      'directeur_etudes', 'enseignant', 'chercheur', 'personnel_administratif', 'scolarite',
      'service_social', 'service_ri', 'bibliothecaire', 'comptable', 'etudiant', 'doctorant', 'parent'];
  return (
    <ResourceManager
      key={variant}
      variant={variant}
      resource="utilisateurs/comptes"
      title="Utilisateurs"
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
};

export default UtilisateursPage;
