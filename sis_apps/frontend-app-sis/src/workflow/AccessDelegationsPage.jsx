import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Chip, Tab, Tabs,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useCapabilities } from '../components/auth/PermissionGuard';
import { PageHeader, SISDataTable, WorkflowHistoryPanel } from '../components/common';
import RecordsTabs from '../components/common/RecordsTabs';
import ResourceManager from '../components/common/ResourceManager';
import { fetchApi } from '../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../services/resources';

const missionStatus = cell => (
  <Chip
    size="small"
    color={cell.value === 'active' ? 'success' : 'default'}
    label={{
      active: 'Active', planifiee: 'Planifiée', expiree: 'Expirée', revoquee: 'Révoquée',
    }[cell.value]}
  />
);

const columns = [
  { Header: 'Bénéficiaire', accessor: 'beneficiaire_nom' },
  { Header: 'Responsable', accessor: 'responsable_nom' },
  { Header: 'Début', accessor: 'debut' },
  { Header: 'Fin', accessor: 'fin' },
  { Header: 'Statut', accessor: 'statut', Cell: missionStatus },
  { Header: 'Mission', accessor: 'motif' },
];

const AccessDelegationsPage = ({ variant }) => {
  const [tab, setTab] = useState(0);
  const [selected, setSelected] = useState(null);
  const capabilities = useCapabilities(variant);
  const url = resourceUrl(variant, 'core/delegations');
  const catalogue = useQuery({ queryKey: ['delegation-catalogue', url], queryFn: () => fetchApi(`${url}catalogue/`) });
  const detail = useQuery({
    queryKey: ['resource', url, selected],
    queryFn: () => fetchApi(`${url}${selected}/`),
    enabled: Boolean(selected),
  });
  const records = useQuery({
    queryKey: ['resource', url, selected, 'dossiers'],
    queryFn: () => fetchAllResourcePages(`${url}${selected}/dossiers/`),
    enabled: Boolean(selected && detail.data?.statut === 'active'),
  });
  const manage = capabilities.data?.permissions?.includes('*')
    || (!['eleve', 'etudiant', 'doctorant'].includes(capabilities.data?.role)
      && capabilities.data?.permissions?.includes('core.manage_accessdelegation'));
  if (capabilities.isLoading || catalogue.isPending) { return <Alert severity="info">Chargement des missions…</Alert>; }
  if (capabilities.error || catalogue.error) {
    return <Alert severity="error">{apiErrorMessage(capabilities.error || catalogue.error)}</Alert>;
  }
  const resource = catalogue.data[tab]?.code;
  return (
    <>
      <Alert severity="info" sx={{ mb: 3 }}>
        Les missions donnent un accès de consultation aux seuls dossiers sélectionnés, pendant la période autorisée.
        Elles ne changent ni votre rôle étudiant ni vos droits de modification ou de signature.
      </Alert>
      <Tabs value={tab} onChange={(_, value) => { setTab(value); setSelected(null); }} aria-label="Ressources délégables">
        {catalogue.data.map(item => <Tab key={item.code} label={item.label} />)}
      </Tabs>
      {!selected && (
      <Box sx={{ mt: 3 }}>
        <ResourceManager
          key={resource}
          variant={variant}
          resource="core/delegations"
          title={manage ? 'Accès délégués' : 'Mes missions'}
          columns={columns}
          filters={{ ressource: resource }}
          fixedValues={{ ressource: resource }}
          allowCreate={Boolean(manage)}
          allowEdit={false}
          onSelect={row => setSelected(row.id)}
          fields={[
            {
              name: 'beneficiaire', label: 'Apprenant', resource: 'core/delegations/beneficiaires', labelField: 'label', required: true,
            },
            {
              name: 'dossiers_ids', label: 'Dossiers autorisés', resource: 'core/delegations/choix', labelField: 'label', filters: { ressource: resource }, multiple: true, required: true,
            },
            {
              name: 'debut', label: 'Début de la mission', type: 'datetime-local', required: true,
            },
            {
              name: 'fin', label: 'Fin de la mission', type: 'datetime-local', required: true,
            },
            {
              name: 'motif', label: 'Objet de la mission et justification', multiline: true, required: true,
            },
          ]}
          actions={manage ? [{
            label: 'Révoquer',
            endpoint: 'revoquer',
            statuses: ['active', 'planifiee'],
            fields: [{
              name: 'motif', label: 'Motif de révocation', required: true, multiline: true,
            }],
          }] : []}
        />
      </Box>
      )}
      {selected && (
        <Box sx={{ mt: 3 }}>
          <Button onClick={() => setSelected(null)}>Retour aux missions</Button>
          <PageHeader title="Détail de la mission" />
          <RecordsTabs
            label="Détails de la mission"
            panels={[
              {
                label: 'Dossiers autorisés',
                content: (
                  <>
                    {(detail.error || records.error) && <Alert severity="error">{apiErrorMessage(detail.error || records.error)}</Alert>}
                    {detail.data?.statut !== 'active' && !detail.isPending && !detail.error && (
                    <Alert severity="info">Cette mission n’est pas active. Son historique reste consultable.</Alert>
                    )}
                    {detail.data?.statut === 'active' && !detail.error && !records.error && (
                    <SISDataTable
                      title="Dossiers de la mission"
                      columns={[
                        { Header: 'Dossier', accessor: 'label' },
                        { Header: 'Statut', accessor: 'statut' },
                        { Header: 'Date de fin', accessor: 'date_fin' },
                      ]}
                      data={records.data || []}
                      loading={records.isPending}
                      exportable={false}
                      onRefresh={() => { detail.refetch(); records.refetch(); }}
                    />
                    )}
                  </>
                ),
              },
              { label: 'Historique', content: <WorkflowHistoryPanel apiType={variant} endpoint={`core/delegations/${selected}/historique/`} title="Historique de la mission" /> },
            ]}
          />
        </Box>
      )}
    </>
  );
};
AccessDelegationsPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default AccessDelegationsPage;
