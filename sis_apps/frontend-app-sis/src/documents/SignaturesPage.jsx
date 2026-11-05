import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Tab, Tabs, Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useCapabilities } from '../components/auth/PermissionGuard';
import {
  PageHeader, SISDataTable, WorkflowHistoryPanel,
} from '../components/common';
import ResourceManager from '../components/common/ResourceManager';
import RecordsTabs from '../components/common/RecordsTabs';
import { fetchApi } from '../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../services/resources';

const columns = [
  { Header: 'Titulaire', accessor: 'titulaire_nom' }, { Header: 'Fonction', accessor: 'fonction' },
  { Header: 'Début', accessor: 'debut' }, { Header: 'Fin', accessor: 'fin' },
  { Header: 'Statut', accessor: 'statut_display' },
];
const decisionAction = (label, decision, statuses) => ({
  label,
  endpoint: 'decider',
  statuses,
  fields: [
    {
      name: 'decision', label: 'Décision', choices: [{ value: decision, label }], defaultValue: decision, required: true,
    },
    {
      name: 'motif', label: 'Justification et contrôles effectués', multiline: true, required: true,
    },
  ],
});

const SignaturesPage = ({ variant }) => {
  const capabilities = useCapabilities(variant);
  const permissions = capabilities.data?.permissions || [];
  const can = permission => permissions.includes('*') || (
    !['eleve', 'etudiant', 'doctorant', 'parent'].includes(capabilities.data?.role) && permissions.includes(permission)
  );
  const [tab, setTab] = useState('personnel');
  const [selected, setSelected] = useState(null);
  const url = resourceUrl(variant, 'core/signatures');
  const types = useQuery({ queryKey: ['signature-types', variant], queryFn: () => fetchApi(`${url}types/`) });
  const usages = useQuery({
    queryKey: ['resource', url, selected, 'usages'],
    queryFn: () => fetchAllResourcePages(`${url}${selected}/usages/`),
    enabled: Boolean(selected && tab !== 'mandats'),
  });
  if (capabilities.isLoading || types.isPending) { return <Alert severity="info">Chargement des signatures…</Alert>; }
  if (capabilities.error || types.error) { return <Alert severity="error">{apiErrorMessage(capabilities.error || types.error)}</Alert>; }
  if (!['request_signature', 'approve_signature', 'use_signature'].some(permission => can(`core.${permission}`))) {
    return <Alert severity="warning">La gestion des signatures exige une habilitation explicite.</Alert>;
  }
  const signatureFields = [
    {
      name: 'fonction', label: 'Fonction institutionnelle', required: true,
    },
    {
      name: 'types_documents', label: 'Types de documents autorisés', multiple: true, choices: types.data, required: true,
    },
    {
      name: 'debut', label: 'Début de validité', type: 'datetime-local', required: true,
    },
    {
      name: 'fin', label: 'Fin de validité', type: 'datetime-local', required: true,
    },
  ];
  return (
    <>
      <PageHeader title="Signatures institutionnelles" subtitle="Identités approuvées, mandats explicites et historique des appositions." />
      <Alert severity="info" sx={{ mb: 3 }}>
        Une autre personne habilitée doit approuver votre signature.
        Vous êtes notifié à chaque apposition, y compris par un mandataire.
        La clé privée est chiffrée et n’est jamais transmise au navigateur.
        La preuve détachée n’est pas une signature juridiquement qualifiée.
      </Alert>
      <Tabs value={tab} onChange={(_, value) => { setTab(value); setSelected(null); }} variant="scrollable" aria-label="Gestion des signatures">
        <Tab value="personnel" label="Mes signatures" />
        {can('core.approve_signature') && <Tab value="validation" label="Validations indépendantes" />}
        <Tab value="mandats" label="Délégations de signature" />
      </Tabs>
      {!selected && (
      <Box sx={{ mt: 3 }}>
        {tab === 'mandats' ? (
          <ResourceManager
            headingLevel={2}
            variant={variant}
            resource="core/mandats-signature"
            title="Délégations de signature"
            allowCreate={can('core.request_signature') && can('core.use_signature')}
            allowEdit={false}
            searchable={false}
            columns={[
              { Header: 'Titulaire', accessor: 'titulaire_nom' }, { Header: 'Opérateur', accessor: 'operateur_nom' },
              { Header: 'Début', accessor: 'debut' }, { Header: 'Fin', accessor: 'fin' },
              { Header: 'Statut', accessor: 'statut' }, { Header: 'Justification', accessor: 'motif' },
            ]}
            fields={[
              {
                name: 'signature',
                label: 'Votre signature',
                resource: 'core/signatures',
                valueType: 'string',
                filters: { vue: 'personnel' },
                labelField: 'fonction',
                required: true,
              },
              {
                name: 'operateur', label: 'Opérateur habilité', resource: 'core/signatures/operateurs', labelField: 'label', required: true,
              },
              ...signatureFields.slice(2),
              {
                name: 'motif', label: 'Objet de la délégation', multiline: true, required: true,
              },
            ]}
            actions={[{
              label: 'Révoquer',
              endpoint: 'revoquer',
              statuses: ['actif', 'planifie'],
              fields: [{
                name: 'motif', label: 'Motif de révocation', required: true, multiline: true,
              }],
            }]}
          />
        ) : (
          <ResourceManager
            headingLevel={2}
            key={tab}
            variant={variant}
            resource="core/signatures"
            title={tab === 'personnel' ? 'Mes signatures' : 'Signatures à contrôler'}
            filters={{ vue: tab }}
            columns={columns}
            fields={signatureFields}
            allowCreate={tab === 'personnel' && can('core.request_signature')}
            allowEdit={false}
            searchable={false}
            onSelect={row => setSelected(row.id)}
            actions={[
              ...(tab === 'validation' ? [
                decisionAction('Valider', 'validee', ['en_attente', 'suspendue']),
                decisionAction('Refuser', 'refusee', ['en_attente']),
              ] : []),
              decisionAction('Suspendre', 'suspendue', ['validee']),
              decisionAction('Révoquer', 'revoquee', ['en_attente', 'validee', 'suspendue']),
            ]}
          />
        )}
      </Box>
      )}
      {selected && tab !== 'mandats' && (
        <Box sx={{ mt: 3 }}>
          <Button onClick={() => setSelected(null)}>Retour aux signatures</Button>
          <Typography variant="h5" component="h2">Utilisations de cette signature</Typography>
          <RecordsTabs
            label="Détails de la signature"
            panels={[
              {
                label: 'Appositions',
                content: usages.error ? <Alert severity="error">{apiErrorMessage(usages.error)}</Alert> : (
                  <SISDataTable
                    title="Appositions"
                    columns={[
                      { Header: 'Date', accessor: 'date' }, { Header: 'Document', accessor: 'type' },
                      { Header: 'Version', accessor: 'version' }, { Header: 'Opérateur', accessor: 'operateur' },
                      { Header: 'Mandat', accessor: 'mandat' }, { Header: 'Empreinte du PDF', accessor: 'sha256' },
                    ]}
                    data={usages.data || []}
                    loading={usages.isPending}
                    exportable={false}
                  />
                ),
              },
              { label: 'Historique', content: <WorkflowHistoryPanel apiType={variant} endpoint={`core/signatures/${selected}/historique/`} title="Historique des décisions" /> },
            ]}
          />
        </Box>
      )}
    </>
  );
};
SignaturesPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default SignaturesPage;
