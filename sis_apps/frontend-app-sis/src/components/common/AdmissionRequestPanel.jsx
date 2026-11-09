import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, CircularProgress, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { postApi } from '../../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../../services/resources';
import WorkflowHistoryPanel from './WorkflowHistoryPanel';

const AdmissionRequestPanel = ({ variant }) => {
  const school = variant === 'secondaire';
  const resource = school ? 'eleves/inscriptions' : 'inscriptions';
  const url = resourceUrl(variant, resource);
  const client = useQueryClient();
  const [year, setYear] = useState('');
  const [target, setTarget] = useState('');
  const [path, setPath] = useState('');
  const [reason, setReason] = useState('');
  const enrollments = useQuery({
    queryKey: ['learner-admissions', variant],
    queryFn: ({ signal }) => fetchAllResourcePages(url, {}, { signal }),
  });
  const canDeposit = enrollments.isSuccess && enrollments.data.length === 0;
  const catalogue = useQuery({
    queryKey: ['admission-catalogue', variant],
    enabled: canDeposit,
    queryFn: async ({ signal }) => {
      const [years, targets, paths] = await Promise.all([
        fetchAllResourcePages(resourceUrl(variant, 'etablissement/annees'), {}, { signal }),
        fetchAllResourcePages(resourceUrl(variant, school ? 'classes/classes' : 'formations/formations'), {}, { signal }),
        school ? [] : fetchAllResourcePages(resourceUrl(variant, 'formations/parcours'), {}, { signal }),
      ]);
      return { years, targets, paths };
    },
  });
  const deposit = useMutation({
    mutationFn: () => postApi(`${url}deposer/`, {
      [school ? 'annee_scolaire' : 'annee_universitaire']: Number(year),
      [school ? 'classe' : 'formation']: Number(target),
      ...(!school && path ? { parcours: Number(path) } : {}),
      motif: reason.trim(),
    }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['learner-admissions', variant] });
      client.invalidateQueries({ queryKey: ['resource'] });
    },
  });

  if (enrollments.isLoading) { return <CircularProgress aria-label="Chargement des admissions" />; }
  if (enrollments.error) {
    return (
      <Alert severity="error">
        Impossible de charger vos inscriptions. {apiErrorMessage(enrollments.error)}
        <Button onClick={() => enrollments.refetch()}>Réessayer</Button>
      </Alert>
    );
  }
  const targets = (catalogue.data?.targets || []).filter(item => !school || item.annee_scolaire === Number(year));
  const paths = (catalogue.data?.paths || []).filter(item => item.formation === Number(target));
  return (
    <Box component="section" aria-label="Mes admissions et inscriptions">
      {deposit.isSuccess && <Alert severity="success">Votre demande a été déposée. La scolarité doit maintenant l’examiner.</Alert>}
      {enrollments.data?.length > 0 && (
        <Stack spacing={2}>
          <Alert severity="info">
            Pour une réinscription, un transfert, une suspension ou une reprise, contactez la scolarité.
            Les décisions et leurs motifs restent consultables ci-dessous.
          </Alert>
          {enrollments.data.map(item => (
            <Box key={item.id}>
              <Typography component="h2" variant="h6">
                {item.annee_libelle || item.annee_universitaire_libelle} — {item.classe_nom || item.formation_nom}
              </Typography>
              <Typography>{item.statut_display}</Typography>
              <WorkflowHistoryPanel
                apiType={variant}
                endpoint={`${resource}/${item.id}/historique/`}
                title="Décisions et historique de l’inscription"
              />
            </Box>
          ))}
        </Stack>
      )}
      {canDeposit && (
        <Box component="form" onSubmit={(event) => { event.preventDefault(); deposit.mutate(); }}>
          <Alert severity="info" sx={{ mb: 2 }}>
            Votre profil existe déjà. Déposez ici votre première demande ; aucune classe
            ni formation n’est affectée automatiquement. Ce formulaire n’est pas un portail de candidature public.
          </Alert>
          {catalogue.isLoading && <CircularProgress aria-label="Chargement des années et formations" />}
          {catalogue.error && (
            <Alert severity="error">
              {apiErrorMessage(catalogue.error)}
              <Button onClick={() => catalogue.refetch()}>Recharger les choix</Button>
            </Alert>
          )}
          {deposit.error && <Alert severity="error">{apiErrorMessage(deposit.error)}</Alert>}
          <Stack spacing={2}>
            <TextField
              select
              required
              label="Année de la demande"
              value={year}
              onChange={(event) => { setYear(event.target.value); setTarget(''); setPath(''); }}
              disabled={catalogue.isLoading || deposit.isPending}
            >
              {(catalogue.data?.years || []).filter(item => !item.cloturee).map(item => (
                <MenuItem key={item.id} value={item.id}>{item.libelle}</MenuItem>
              ))}
            </TextField>
            <TextField
              select
              required
              label={school ? 'Classe demandée' : 'Formation demandée'}
              value={target}
              onChange={(event) => { setTarget(event.target.value); setPath(''); }}
              disabled={!year || catalogue.isLoading || deposit.isPending}
            >
              {targets.map(item => <MenuItem key={item.id} value={item.id}>{item.nom}</MenuItem>)}
            </TextField>
            {!school && paths.length > 0 && (
              <TextField select label="Parcours (facultatif)" value={path} onChange={event => setPath(event.target.value)} disabled={deposit.isPending}>
                <MenuItem value="">—</MenuItem>
                {paths.map(item => <MenuItem key={item.id} value={item.id}>{item.nom}</MenuItem>)}
              </TextField>
            )}
            <TextField
              label="Message à la scolarité"
              multiline
              value={reason}
              onChange={event => setReason(event.target.value)}
              slotProps={{ htmlInput: { maxLength: 2000 } }}
              disabled={deposit.isPending}
            />
            <Button type="submit" variant="contained" disabled={!year || !target || Boolean(catalogue.error) || deposit.isPending}>
              {deposit.isPending ? 'Dépôt en cours…' : 'Déposer ma première demande'}
            </Button>
          </Stack>
        </Box>
      )}
    </Box>
  );
};

AdmissionRequestPanel.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
};

export default AdmissionRequestPanel;
