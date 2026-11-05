import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Chip, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useCapabilities } from '../components/auth/PermissionGuard';
import { WorkflowHistoryPanel } from '../components/common';
import ResourceManager from '../components/common/ResourceManager';
import { fetchApi, postApi } from '../services/api';
import {
  apiErrorMessage, downloadJson, downloadPdf, resourceUrl,
} from '../services/resources';

const archiveStatus = cell => (
  <Chip size="small" label={cell.value === 'revoque' ? 'Révoquée' : 'Émise'} color={cell.value === 'revoque' ? 'warning' : 'success'} />
);
const columns = [
  { Header: 'Document', accessor: 'source_type' }, { Header: 'Dossier', accessor: 'source_id' },
  { Header: 'Bénéficiaire', accessor: 'beneficiaire_nom' }, { Header: 'Titulaire de signature', accessor: 'titulaire_nom' },
  { Header: 'Version', accessor: 'version' }, { Header: 'Date', accessor: 'created_at' },
  { Header: 'Statut', accessor: 'statut', Cell: archiveStatus },
];

const ArchivedDocuments = ({ variant }) => {
  const capabilities = useCapabilities(variant);
  const permissions = capabilities.data?.permissions || [];
  const can = permission => permissions.includes('*') || (
    !['eleve', 'etudiant', 'doctorant', 'parent'].includes(capabilities.data?.role) && permissions.includes(permission)
  );
  const canSign = can('core.use_signature');
  const [type, setType] = useState(variant === 'secondaire' ? 'notes.bulletin' : 'releves.relevenotes');
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [selected, setSelected] = useState(null);
  const [file, setFile] = useState(null);
  const url = resourceUrl(variant, 'core/documents-signes');
  const types = useQuery({
    queryKey: ['signature-types', variant],
    queryFn: () => fetchApi(resourceUrl(variant, 'core/signatures/types')),
    enabled: canSign,
  });
  const detail = useQuery({
    queryKey: ['resource', url, selected],
    queryFn: () => fetchApi(`${url}${selected}/`),
    enabled: Boolean(selected),
  });
  const download = useMutation({
    mutationFn: format => (format === 'pdf'
      ? downloadPdf(`${url}${selected}/pdf/`, `archive-${selected}.pdf`)
      : downloadJson(`${url}${selected}/preuve/`, `preuve-${selected}.json`)),
  });
  const verify = useMutation({
    mutationFn: () => {
      const body = file ? new FormData() : {};
      if (file) { body.append('pdf', file); }
      return postApi(`${url}${selected}/verifier/`, body);
    },
  });
  if (capabilities.isLoading) { return <Alert severity="info">Chargement des archives…</Alert>; }
  if (capabilities.error || types.error) { return <Alert severity="error">{apiErrorMessage(capabilities.error || types.error)}</Alert>; }
  return (
    <Box sx={{ mt: 2 }}>
      <Alert severity="info" sx={{ mb: 3 }}>
        Chaque apposition conserve une version du PDF et une preuve Ed25519 détachée,
        et notifie le titulaire de la signature.
        Ce mécanisme n’est pas une signature juridiquement qualifiée.
        Une correction crée une nouvelle version ; une révocation ne supprime pas l’ancienne.
      </Alert>
      {canSign && (
        <TextField select fullWidth label="Type du document à signer" value={type} onChange={event => setType(event.target.value)} sx={{ mb: 3 }}>
          {(types.data || []).map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
        </TextField>
      )}
      <ResourceManager
        key={type}
        variant={variant}
        resource="core/documents-signes"
        title="Versions signées et archivées"
        columns={columns}
        allowCreate={canSign}
        allowEdit={false}
        searchable={false}
        fixedValues={{ source_type: type, idempotency_key: key }}
        onSaved={() => setKey(crypto.randomUUID())}
        onSelect={row => { setSelected(row.id); setFile(null); download.reset(); verify.reset(); }}
        fields={[
          {
            name: 'signature',
            label: 'Signature approuvée',
            resource: 'core/signatures',
            filters: { vue: 'utilisables' },
            labelField: 'fonction',
            valueType: 'string',
            required: true,
          },
          {
            name: 'source_id',
            label: 'Document publié ou validé',
            resource: 'core/documents-signes/sources',
            filters: { source_type: type },
            labelField: 'label',
            required: true,
          },
        ]}
        actions={can('core.revoke_documentarchive') ? [{
          label: 'Révoquer la version',
          endpoint: 'revoquer',
          statuses: ['valide'],
          fields: [{
            name: 'motif', label: 'Motif de révocation', required: true, multiline: true,
          }],
        }] : []}
      />
      {selected && (
        <Box component="section" aria-label="Preuve du document" sx={{ mt: 3, minWidth: 0 }}>
          <Typography variant="h5" component="h2">Preuve du document</Typography>
          {(detail.error || download.error || verify.error) && <Alert severity="error">{apiErrorMessage(detail.error || download.error || verify.error)}</Alert>}
          {detail.data?.statut === 'revoque' && <Alert severity="warning">Version révoquée : {detail.data.motif_revocation}</Alert>}
          <Typography variant="body2" sx={{ overflowWrap: 'anywhere', my: 2 }}>SHA-256 : {detail.data?.sha256}</Typography>
          <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap', mb: 2 }}>
            <Button disabled={download.isPending || detail.isPending || Boolean(detail.error)} onClick={() => download.mutate('pdf')}>Télécharger le PDF archivé</Button>
            <Button disabled={download.isPending || detail.isPending || Boolean(detail.error)} onClick={() => download.mutate('json')}>Télécharger la preuve JSON</Button>
          </Stack>
          <TextField
            key={selected}
            label="PDF à comparer (facultatif)"
            type="file"
            fullWidth
            slotProps={{ inputLabel: { shrink: true }, htmlInput: { accept: '.pdf,application/pdf' } }}
            onChange={event => { setFile(event.target.files[0] || null); verify.reset(); }}
            helperText="Sans fichier, la version conservée par l’établissement est vérifiée."
          />
          <Button
            sx={{ my: 2 }}
            disabled={verify.isPending || detail.isPending || Boolean(detail.error)}
            onClick={() => verify.mutate()}
          >
            Vérifier l’intégrité
          </Button>
          {verify.data && (
            <Alert severity={verify.data.statut === 'revoque' ? 'warning' : 'success'} sx={{ overflowWrap: 'anywhere' }}>
              Intégrité confirmée.
              {' '}{verify.data.statut === 'revoque' ? 'Attention : cette version est révoquée.' : 'Version non révoquée.'}
              {' '}Empreinte de la clé : {verify.data.empreinte_cle}. {verify.data.qualification}
            </Alert>
          )}
          <WorkflowHistoryPanel apiType={variant} endpoint={`core/documents-signes/${selected}/historique/`} title="Historique de la version" />
        </Box>
      )}
    </Box>
  );
};
ArchivedDocuments.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default ArchivedDocuments;
