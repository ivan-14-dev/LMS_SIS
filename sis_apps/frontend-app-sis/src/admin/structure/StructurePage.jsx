import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, MenuItem, TextField } from '@mui/material';
import ResourceManager from '../../components/common/ResourceManager';
import { getEnabledVariants } from '../../services/resources';

const codeName = [
  { name: 'code', label: 'Code', required: true },
  { name: 'nom', label: 'Nom', required: true },
];

const secondaryResources = [
  {
    resource: 'etablissement/niveaux',
    title: 'Niveaux',
    fields: [
      codeName[0], { name: 'libelle', label: 'Libellé', required: true },
      {
        name: 'ordre', label: 'Ordre', type: 'number', required: true,
      },
      { name: 'cycle', label: 'Cycle', required: true },
    ],
  },
  {
    resource: 'classes/matieres',
    title: 'Matières',
    fields: codeName,
  },
  {
    resource: 'salles',
    title: 'Salles',
    fields: [
      ...codeName, {
        name: 'capacite', label: 'Capacité', type: 'number', required: true,
      },
      { name: 'batiment', label: 'Bâtiment' }, {
        name: 'etage', label: 'Étage', type: 'number', defaultValue: 0,
      },
    ],
  },
];
const higherResources = [
  {
    resource: 'structure/facultes',
    title: 'Facultés',
    fields: [
      ...codeName, {
        name: 'date_creation', label: 'Date de création', type: 'date', required: true,
      },
      {
        name: 'doyen', label: 'Doyen', resource: 'utilisateurs/comptes', labelField: 'full_name',
      },
    ],
  },
  {
    resource: 'structure/departements',
    title: 'Départements',
    fields: [...codeName, {
      name: 'faculte', label: 'Faculté', resource: 'structure/facultes', required: true,
    }],
  },
  {
    resource: 'structure/ecoles-doctorales',
    title: 'Écoles doctorales',
    fields: codeName,
  },
];

const StructurePage = () => {
  const [params] = useSearchParams();
  const [selected, setSelected] = useState(0);
  const enabled = getEnabledVariants();
  const variant = enabled.includes(params.get('sis')) ? params.get('sis') : enabled[0];
  const options = variant === 'secondaire' ? secondaryResources : higherResources;
  const active = options[selected];
  return (
    <Box>
      <TextField select label="Structure" value={selected} onChange={event => setSelected(event.target.value)} sx={{ mb: 3, minWidth: 250 }}>
        {options.map((item, index) => <MenuItem value={index} key={item.resource}>{item.title}</MenuItem>)}
      </TextField>
      <ResourceManager
        key={`${variant}-${active.resource}`}
        variant={variant}
        resource={active.resource}
        title={active.title}
        fields={active.fields}
        searchable={false}
        columns={[
          { Header: 'Code', accessor: 'code' },
          { Header: 'Nom', accessor: active.resource === 'etablissement/niveaux' ? 'libelle' : 'nom' },
        ]}
      />
    </Box>
  );
};
export default StructurePage;
