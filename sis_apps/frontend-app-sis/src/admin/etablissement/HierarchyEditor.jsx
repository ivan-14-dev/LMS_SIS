import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Checkbox, FormControlLabel, MenuItem, Paper, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ResourceManager from '../../components/common/ResourceManager';
import { fetchApi, patchApi, postApi } from '../../services/api';
import { apiErrorMessage, fetchAllResourcePages } from '../../services/resources';
import OrganizationAttachments from './OrganizationAttachments';

const setting = 'learning.offering';

const RulesEditor = ({ endpoint, unit, offerings }) => {
  const client = useQueryClient();
  const url = `${endpoint}hierarchy/`;
  const queryKey = ['hierarchy', url, unit];
  const query = useQuery({
    queryKey,
    queryFn: () => fetchApi(`${url}${unit ? `?unit=${unit}` : ''}`),
    refetchOnWindowFocus: false,
  });
  const [mode, setMode] = useState('inherit');
  const [offering, setOffering] = useState(null);
  const [locked, setLocked] = useState(false);
  const [reason, setReason] = useState('');
  const [date, setDate] = useState('');
  const [inspectionDate, setInspectionDate] = useState('');
  const inspection = useMutation({
    mutationFn: at => fetchApi(`${url}?${new URLSearchParams({ ...(unit ? { unit } : {}), at })}`),
  });
  const preview = useMutation({ mutationFn: payload => postApi(url, payload) });
  const publication = useMutation({
    mutationFn: payload => patchApi(url, payload),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['hierarchy', url] });
      preview.reset();
      inspection.reset();
      setReason('');
      setDate('');
    },
  });
  useEffect(() => {
    if (!query.data) { return; }
    const { local } = query.data.effective;
    const localMode = local.values[setting] === null ? 'none' : 'offering';
    setMode(Object.hasOwn(local.values, setting) ? localMode : 'inherit');
    setOffering(local.values[setting] || null);
    setLocked(local.locks.includes(setting));
  }, [query.data]);
  const reset = () => { preview.reset(); publication.reset(); inspection.reset(); };
  if (query.isPending) { return <p role="status">Chargement des règles héritées…</p>; }
  if (query.isError) {
    return <Alert severity="error">{apiErrorMessage(query.error)}<Button onClick={() => query.refetch()}>Recharger les règles</Button></Alert>;
  }
  const { effective } = query.data;
  const result = preview.data?.effective || inspection.data?.effective || effective;
  const chosen = result.values[setting];
  const origin = result.origins[setting];
  const historicalOffering = offering && !offerings.some(item => item.code === offering.code);
  const options = historicalOffering ? [...offerings, offering] : offerings;
  const busy = preview.isPending || publication.isPending || inspection.isPending;
  const payload = {
    unit: unit ? Number(unit) : null,
    base_revision: query.data.revision,
    values: mode === 'inherit' ? {} : { [setting]: mode === 'none' ? null : offering },
    locks: mode !== 'inherit' && locked ? [setting] : [],
    reason,
    effective_from: date ? new Date(date).toISOString() : null,
  };
  const valid = reason.trim() && (mode !== 'offering' || offering);
  let resolutionLabel = 'Configuration actuellement effective.';
  if (inspection.isSuccess) { resolutionLabel = 'Configuration à la date consultée.'; }
  if (preview.isSuccess) { resolutionLabel = 'Simulation — aucun changement enregistré.'; }
  return (
    <Paper component="section" variant="outlined" sx={{ p: 3, mt: 3 }}>
      <Typography component="h2" variant="h6">Règles héritées et publication</Typography>
      <Alert severity="info" sx={{ my: 2 }}>
        L’offre est copiée à la création des nouvelles classes/formations.
        Les classes, formations, inscriptions et résultats existants ne sont jamais recalculés.
        Chaque publication remplace les valeurs locales de ce périmètre à sa date d’effet.
      </Alert>
      <Stack spacing={2}>
        <TextField
          select
          label="Règle d’offre"
          value={mode}
          disabled={busy}
          onChange={(event) => { setMode(event.target.value); setLocked(false); reset(); }}
        >
          <MenuItem value="inherit">Hériter du périmètre supérieur</MenuItem>
          <MenuItem value="none">Aucune offre par défaut</MenuItem>
          <MenuItem value="offering">Choisir une offre institutionnelle</MenuItem>
        </TextField>
        {mode === 'offering' && (
          <TextField
            select
            label="Offre à publier"
            value={offering?.code || ''}
            disabled={busy}
            onChange={(event) => { setOffering(options.find(item => item.code === event.target.value)); reset(); }}
          >
            <MenuItem value="">Sélectionner</MenuItem>
            {options.map(item => <MenuItem key={item.code} value={item.code}>{item.label}</MenuItem>)}
          </TextField>
        )}
        <FormControlLabel
          label="Verrouiller cette valeur pour les périmètres inférieurs"
          control={<Checkbox checked={locked} disabled={mode === 'inherit' || busy} onChange={(event) => { setLocked(event.target.checked); reset(); }} />}
        />
        <TextField
          label="Date d’effet (heure de cet appareil, vide : maintenant)"
          type="datetime-local"
          value={date}
          slotProps={{ inputLabel: { shrink: true } }}
          disabled={busy}
          onChange={(event) => { setDate(event.target.value); reset(); }}
        />
        <TextField label="Motif de publication" value={reason} disabled={busy} onChange={(event) => { setReason(event.target.value); reset(); }} />
        {(preview.error || publication.error || inspection.error) && (
          <Alert severity="error">
            {apiErrorMessage(publication.error || preview.error || inspection.error)}
            <Button onClick={() => { reset(); query.refetch(); }}>Recharger les règles</Button>
          </Alert>
        )}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          <Button variant="outlined" disabled={!valid || busy} onClick={() => preview.mutate(payload)}>Simuler les règles</Button>
          <Button variant="contained" disabled={!valid || busy || !preview.isSuccess} onClick={() => publication.mutate(payload)}>Publier les règles</Button>
        </Box>
        {publication.isSuccess && <Alert severity="success">Configuration publiée. Les dossiers existants sont conservés.</Alert>}
        <Alert severity={preview.isSuccess ? 'info' : 'success'}>
          {resolutionLabel}
          <Typography>Date résolue : {new Date(result.at).toLocaleString('fr')}</Typography>
          <Typography>Offre effective : {chosen?.label || 'Aucune'}</Typography>
          <Typography>Origine : {origin.label} · révision {origin.revision}</Typography>
          <Typography>Verrou : {result.locks[setting] ? result.locks[setting].label : 'Aucun'}</Typography>
        </Alert>
        {(preview.data?.impacts?.length > 0 || result.ignored_overrides.length > 0) && (
          <Alert severity="warning">
            Des valeurs locales sont neutralisées par un verrou supérieur.
            {(preview.data?.impacts || []).map(item => <Typography key={item.unit}>{item.nom}</Typography>)}
          </Alert>
        )}
        <TextField
          label="Date à consulter (heure de cet appareil)"
          type="datetime-local"
          value={inspectionDate}
          slotProps={{ inputLabel: { shrink: true } }}
          disabled={busy}
          onChange={event => setInspectionDate(event.target.value)}
        />
        <Button
          variant="outlined"
          disabled={!inspectionDate || busy}
          onClick={() => { reset(); inspection.mutate(new Date(inspectionDate).toISOString()); }}
        >
          Consulter les règles à cette date
        </Button>
        <Typography component="h3" variant="subtitle1">Publications de ce périmètre</Typography>
        {query.data.history.length === 0 && <Typography>Aucune publication locale.</Typography>}
        {query.data.history.map(item => (
          <Box key={item.revision} sx={{ borderTop: 1, borderColor: 'divider', pt: 1 }}>
            <Typography>Révision {item.revision} · effet {new Date(item.effective_from).toLocaleString('fr')}</Typography>
            <Typography>{item.published_by} — {item.reason}</Typography>
          </Box>
        ))}
      </Stack>
    </Paper>
  );
};
RulesEditor.propTypes = {
  endpoint: PropTypes.string.isRequired,
  unit: PropTypes.string.isRequired,
  offerings: PropTypes.arrayOf(PropTypes.shape({
    code: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
  })).isRequired,
};

const HierarchyEditor = ({ endpoint, variant }) => {
  const [unit, setUnit] = useState('');
  const [view, setView] = useState('units');
  const base = endpoint.replace(/current\/$/, '');
  const units = useQuery({
    queryKey: ['reference', `${base}unites/`],
    queryFn: () => fetchAllResourcePages(`${base}unites/`),
  });
  const offerings = useQuery({
    queryKey: ['reference', `${base}learning-offerings/`],
    queryFn: () => fetchAllResourcePages(`${base}learning-offerings/`),
    enabled: view === 'rules',
  });
  const catalogue = useQuery({
    queryKey: ['organization-catalogue', base],
    queryFn: () => fetchApi(`${base}unites/catalogue/`),
  });
  return (
    <Box sx={{ mt: 3, minWidth: 0 }}>
      <Alert severity="info" sx={{ mb: 3 }}>
        Construisez une organisation libre adaptée à votre établissement, sans chaîne de catégories imposée.
        Raccordez explicitement les objets académiques existants dans « Rattachements ».
        Les anciens périmètres conservent leurs règles historiques.
        Codes, catégories, parents et rattachements sont figés ; renommage permis, déplacement et suppression refusés.
      </Alert>
      <Stack component="nav" aria-label="Vues de l’organisation" direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap', mb: 3 }}>
        {[
          ['units', 'Organigramme'], ['attachments', 'Rattachements'], ['rules', 'Règles héritées'],
        ].map(([value, label]) => (
          <Button key={value} variant={view === value ? 'contained' : 'outlined'} aria-pressed={view === value} onClick={() => setView(value)}>{label}</Button>
        ))}
      </Stack>
      {catalogue.isPending && <Typography role="status">Chargement des catégories…</Typography>}
      {catalogue.error && <Alert severity="error">{apiErrorMessage(catalogue.error)}<Button onClick={() => catalogue.refetch()}>Recharger les catégories</Button></Alert>}
      {view === 'units' && catalogue.data && (
      <ResourceManager
        variant={variant}
        resource="etablissement/unites"
        headingLevel={2}
        title="Unités d’organisation"
        onSelect={(row) => { setUnit(String(row.id)); setView('attachments'); }}
        columns={[
          { Header: 'Code', accessor: 'code' }, { Header: 'Nom', accessor: 'nom' },
          { Header: 'Type', accessor: 'kind_label' }, { Header: 'Parent', accessor: 'parent_label' },
          { Header: 'Mode', accessor: 'topology_label' },
        ]}
        fields={[
          {
            name: 'topology_version',
            label: 'Mode de création',
            createOnly: true,
            defaultValue: 2,
            required: true,
            choices: [{ value: 2, label: 'Organisation libre' }],
          },
          {
            name: 'code', label: 'Code de l’unité', required: true, createOnly: true,
          },
          { name: 'nom', label: 'Nom de l’unité', required: true },
          {
            name: 'kind',
            label: 'Type d’unité',
            required: true,
            createOnly: true,
            choices: catalogue.data.kinds,
          },
          { name: 'category_label', label: 'Précision de catégorie (obligatoire pour Autre)' },
          {
            name: 'parent', label: 'Unité parente', resource: 'etablissement/unites', createOnly: true, labelField: 'label',
          },
        ]}
      />
      )}
      {view !== 'units' && (units.error || (view === 'rules' && offerings.error)) && <Alert severity="error">{apiErrorMessage(units.error || offerings.error)}</Alert>}
      {view !== 'units' && !units.error && (
        <>
          <TextField select fullWidth label={view === 'rules' ? 'Périmètre des règles' : 'Unité consultée'} value={unit} onChange={event => setUnit(String(event.target.value))} sx={{ mb: 3 }} slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}>
            <MenuItem value="">{view === 'rules' ? 'Établissement entier' : 'Choisir une unité'}</MenuItem>
            {(units.data || []).map(item => <MenuItem key={item.id} value={String(item.id)}>{item.label}</MenuItem>)}
          </TextField>
          {view === 'rules' && !offerings.error && <RulesEditor key={unit} endpoint={endpoint} unit={unit} offerings={offerings.data || []} />}
          {view === 'attachments' && catalogue.data && <OrganizationAttachments key={unit} base={base} unit={unit} targets={catalogue.data.targets} onUnitChange={setUnit} />}
        </>
      )}
    </Box>
  );
};
HierarchyEditor.propTypes = { endpoint: PropTypes.string.isRequired, variant: PropTypes.string.isRequired };
export default HierarchyEditor;
