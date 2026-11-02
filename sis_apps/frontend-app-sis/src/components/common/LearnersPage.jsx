import React from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import ResourceManager from './ResourceManager';
import LearnerImport from './LearnerImport';

const LearnersPage = ({ variant }) => {
  const navigate = useNavigate();
  const secondary = variant === 'secondaire';
  const resource = secondary ? 'eleves' : 'etudiants';
  const fields = [
    {
      name: 'username', label: 'Identifiant', required: true, createOnly: true,
    },
    {
      name: 'first_name', label: 'Prénom', required: true, createOnly: true,
    },
    {
      name: 'last_name', label: 'Nom', required: true, createOnly: true,
    },
    {
      name: 'email', label: 'Email', type: 'email', required: true, createOnly: true,
    },
    {
      name: 'password', label: 'Mot de passe initial', type: 'password', required: true, createOnly: true,
    },
    ...(!secondary ? [{
      name: 'matricule', label: 'Matricule', required: true, createOnly: true,
    }] : []),
    {
      name: 'date_naissance', label: 'Date de naissance', type: 'date', required: true,
    },
    { name: 'lieu_naissance', label: 'Lieu de naissance', required: true },
    {
      name: 'sexe', label: 'Sexe', required: true, choices: [{ value: 'M', label: 'Masculin' }, { value: 'F', label: 'Féminin' }],
    },
    { name: 'adresse', label: 'Adresse', required: !secondary },
    { name: 'code_postal', label: 'Code postal', required: !secondary },
    { name: 'ville', label: 'Ville', required: !secondary },
    ...(!secondary ? [{ name: 'telephone', label: 'Téléphone', required: true }] : []),
    ...(secondary ? [{ name: 'classe_actuelle', label: 'Classe actuelle', resource: 'classes/classes' }] : []),
  ];
  return (
    <>
      <ResourceManager
        variant={variant}
        resource={resource}
        title={secondary ? 'Élèves' : 'Étudiants'}
        columns={[
          { Header: 'Matricule', accessor: 'matricule' },
          { Header: 'Nom complet', accessor: 'full_name' },
          { Header: 'Email', accessor: 'email' },
          { Header: secondary ? 'Classe' : 'Statut', accessor: secondary ? 'classe_nom' : 'statut_display' },
        ]}
        fields={fields}
        onSelect={record => navigate(`/${variant}/${resource}/${record.id}`)}
      />
      <LearnerImport variant={variant} resource={resource} />
    </>
  );
};

LearnersPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default LearnersPage;
