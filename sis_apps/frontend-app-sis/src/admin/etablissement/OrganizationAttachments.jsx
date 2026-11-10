import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import SISDataTable from '../../components/common/SISDataTable';
import CollectionPagination from '../../components/common/CollectionPagination';
import { fetchApi, postApi } from '../../services/api';
import { apiErrorMessage, fetchResourcePage } from '../../services/resources';

const labels = {
  username: 'Identifiant',
  first_name: 'Prénom',
  last_name: 'Nom',
  is_active: 'Actif',
  nom: 'Nom',
  code: 'Code',
  libelle: 'Libellé',
  titre: 'Titre',
  auteurs: 'Auteurs',
  isbn: 'ISBN',
  resume: 'Résumé',
  description: 'Description',
  niveau: 'Niveau',
  type: 'Type',
  offre_code: 'Offre historisée',
  credits_ects: 'Crédits ECTS',
  specialisation: 'Spécialisation',
  capacite: 'Capacité',
  jour: 'Jour (code du planning)',
  heure_debut: 'Début',
  heure_fin: 'Fin',
  date_specifique: 'Date',
  type_cours: 'Type de cours',
  groupe: 'Groupe (libellé du créneau)',
  semaine_debut: 'Première semaine',
  semaine_fin: 'Dernière semaine',
  'creneau_horaire.heure_debut': 'Début',
  'creneau_horaire.heure_fin': 'Fin',
};
const displayValue = (value) => {
  if (typeof value === 'boolean') { return value ? 'Oui' : 'Non'; }
  return value === null || value === '' ? 'Non renseigné' : String(value);
};
const inspectButton = (inspect, { row }) => (
  <Button onClick={() => inspect(row.original)}>Consulter</Button>
);

const OrganizationAttachments = ({
  base, unit, targets, onUnitChange,
}) => {
  const client = useQueryClient();
  const [kind, setKind] = useState('user');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [adding, setAdding] = useState(false);
  const [candidatePage, setCandidatePage] = useState(1);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [inspection, setInspection] = useState(null);
  const [relationPage, setRelationPage] = useState(1);
  const endpoint = `${base}unites/${unit}/attachments/`;
  const query = useQuery({
    queryKey: ['organization-attachments', endpoint, kind, page, pageSize],
    queryFn: ({ signal }) => fetchResourcePage(endpoint, {
      kind, page: page + 1, page_size: pageSize,
    }, { signal }),
    enabled: Boolean(unit),
  });
  const candidates = useQuery({
    queryKey: ['organization-references', base, kind, search, candidatePage],
    queryFn: ({ signal }) => fetchResourcePage(`${base}unites/references/`, {
      kind, search, page: candidatePage, page_size: 25,
    }, { signal }),
    enabled: adding,
  });
  const detail = useQuery({
    queryKey: ['organization-object', base, unit, kind, inspection?.id, relationPage],
    queryFn: () => fetchApi(`${base}unites/${unit}/attached-object/?${new URLSearchParams({
      kind, object_id: inspection.id, page: relationPage, page_size: 25,
    })}`),
    enabled: Boolean(inspection),
  });
  const saving = useMutation({
    mutationFn: () => postApi(endpoint, { kind, object_id: Number(selected), confirm: confirmed }),
    onSuccess: () => {
      setAdding(false);
      client.invalidateQueries({ queryKey: ['organization-attachments', endpoint] });
      client.invalidateQueries({ queryKey: ['organization-references', base] });
      client.invalidateQueries({ queryKey: ['resource'] });
    },
  });
  const open = () => {
    saving.reset(); setSelected(''); setConfirmed(false); setSearch(''); setCandidatePage(1); setAdding(true);
  };
  const selectionChanged = () => { setSelected(''); setConfirmed(false); };
  const chooseKind = (value) => {
    setKind(value); setPage(0); setInspection(null); saving.reset();
  };
  const inspect = (item) => { setRelationPage(1); setInspection(item); };
  if (!unit) { return <Alert severity="info">Choisissez une unité pour consulter ses rattachements.</Alert>; }
  return (
    <Stack spacing={2}>
      <Alert severity="info">
        Rattachez des objets existants, sans créer de doublons. Aucun droit ni accès LMS n’est accordé.
        Le rattachement initial d’une classe ou formation conserve son offre et sa provenance historiques.
        Les rattachements sont ensuite figés ; les relations académiques existantes restent inchangées.
      </Alert>
      <TextField select label="Objets rattachés" value={kind} onChange={event => chooseKind(event.target.value)}>
        {targets.map(target => <MenuItem key={target.kind} value={target.kind}>{target.label}</MenuItem>)}
      </TextField>
      {saving.isSuccess && <Alert severity="success">Rattachement enregistré par le serveur. Droits et dossiers antérieurs conservés.</Alert>}
      {query.error && <Alert severity="error">{apiErrorMessage(query.error)}</Alert>}
      <SISDataTable
        title="Rattachements de l’unité"
        data={query.data?.results || []}
        columns={[
          { Header: 'Objet existant', accessor: 'label' },
          { Header: 'Identifiant', accessor: 'id' },
          { Header: 'Consultation', accessor: 'kind', Cell: inspectButton.bind(null, inspect) },
        ]}
        searchable={false}
        exportable={false}
        loading={query.isPending}
        onRefresh={() => query.refetch()}
        toolbarActions={<Button variant="contained" onClick={open}>Rattacher un objet existant</Button>}
        serverPagination={{
          page,
          pageSize,
          count: query.data?.count || 0,
          onPageChange: setPage,
          onPageSizeChange: value => { setPageSize(value); setPage(0); },
        }}
      />
      <Dialog open={adding} onClose={() => !saving.isPending && setAdding(false)} fullWidth>
        <DialogTitle>Rattacher un objet existant</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {saving.error && <Alert severity="error">{apiErrorMessage(saving.error)}</Alert>}
            {candidates.error && <Alert severity="error">{apiErrorMessage(candidates.error)}<Button onClick={() => candidates.refetch()}>Réessayer la recherche</Button></Alert>}
            <TextField
              label="Rechercher un objet"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value); setCandidatePage(1); selectionChanged();
              }}
            />
            <TextField
              select
              label="Objet existant à rattacher"
              value={selected}
              disabled={candidates.isPending || candidates.isError || saving.isPending}
              onChange={(event) => { setSelected(String(event.target.value)); setConfirmed(false); }}
            >
              <MenuItem value="">Sélectionner</MenuItem>
              {(candidates.data?.results || []).map(candidate => (
                <MenuItem key={candidate.id} value={String(candidate.id)} disabled={candidate.unit !== null}>
                  {candidate.label}{candidate.unit !== null ? ' — déjà rattaché' : ''}
                </MenuItem>
              ))}
            </TextField>
            {candidates.isPending && <Typography role="status">Recherche en cours…</Typography>}
            {!candidates.isFetching && !candidates.error && candidates.data?.count === 0 && (
              <Typography>Aucun objet trouvé.</Typography>
            )}
            <CollectionPagination
              data={candidates.error ? null : candidates.data}
              page={candidatePage}
              setPage={value => { setCandidatePage(value); selectionChanged(); }}
              disabled={candidates.isFetching || saving.isPending}
              label="Objets existants"
              previousLabel="Références précédentes"
              nextLabel="Références suivantes"
            />
            <FormControlLabel
              label="Je confirme ce rattachement figé, sans modifier les droits ni les règles historisées."
              control={(
                <Checkbox
                  checked={confirmed}
                  disabled={!selected || saving.isPending}
                  onChange={event => setConfirmed(event.target.checked)}
                />
              )}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button disabled={saving.isPending} onClick={() => setAdding(false)}>Annuler</Button>
          <Button variant="contained" disabled={!selected || !confirmed || saving.isPending || candidates.isError} onClick={() => saving.mutate()}>Confirmer le rattachement</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={Boolean(inspection)} onClose={() => setInspection(null)} fullWidth>
        <DialogTitle>Objet rattaché — {inspection?.label}</DialogTitle>
        <DialogContent>
          {detail.isPending && <Typography role="status">Chargement de l’objet…</Typography>}
          {detail.error && <Alert severity="error">{apiErrorMessage(detail.error)}<Button onClick={() => detail.refetch()}>Réessayer la consultation</Button></Alert>}
          {detail.data && (
            <Stack spacing={1}>
              {Object.entries(detail.data.details).map(([key, value]) => (
                <Typography key={key}><strong>{labels[key] || key} :</strong> {displayValue(value)}</Typography>
              ))}
              <Typography variant="h6" component="h3">Relations académiques existantes</Typography>
              {detail.data.relations.length === 0 && <Typography>Aucune relation dans ce catalogue.</Typography>}
              {detail.data.relations.map(related => (
                <Box key={`${related.kind}-${related.id}`}>
                  <Typography>{related.label} · #{related.id}</Typography>
                  {related.unit ? (
                    <Button onClick={() => { setInspection(null); onUnitChange(String(related.unit)); }}>
                      Consulter l’unité {related.unit}
                    </Button>
                  ) : <Typography color="text.secondary">Unité non encore rattachée</Typography>}
                </Box>
              ))}
              {(detail.data.relation_pages || []).some(item => item.next || item.previous) && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  <Button
                    disabled={!detail.data.relation_pages.some(item => item.previous)}
                    onClick={() => setRelationPage(value => value - 1)}
                  >
                    Relations précédentes
                  </Button>
                  <Button
                    disabled={!detail.data.relation_pages.some(item => item.next)}
                    onClick={() => setRelationPage(value => value + 1)}
                  >
                    Relations suivantes
                  </Button>
                </Box>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions><Button onClick={() => setInspection(null)}>Fermer</Button></DialogActions>
      </Dialog>
    </Stack>
  );
};

OrganizationAttachments.propTypes = {
  base: PropTypes.string.isRequired,
  unit: PropTypes.string.isRequired,
  targets: PropTypes.arrayOf(PropTypes.shape({
    kind: PropTypes.string.isRequired, label: PropTypes.string.isRequired,
  })).isRequired,
  onUnitChange: PropTypes.func.isRequired,
};

export default OrganizationAttachments;
