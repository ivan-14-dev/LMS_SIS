import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Button, Paper, Stack, TextField, Typography,
} from '@mui/material';
import { PageHeader, SISDataTable } from '../components/common';
import { fetchApi } from '../services/api';
import { apiErrorMessage, fetchAllResourcePages } from '../services/resources';
import ProjectCommandDialog from './ProjectCommandDialog';
import ProjectTeamPanel from './ProjectTeamPanel';
import {
  bindingLabel, competencyLabel, dateLabel, isDenied, queryOptions, rules, selectProps,
} from './projectUi';

const milestoneColumns = [
  { Header: 'Ordre', accessor: 'ordre' },
  { Header: 'Jalon', accessor: 'titre' },
  { Header: 'Échéance', accessor: 'echeance', Cell: ({ value }) => dateLabel(value) },
  { Header: 'Barème', accessor: 'bareme' },
];
const ProjectDetail = ({
  url, id, busy, onBusy, onBack, onDenied,
}) => {
  const client = useQueryClient();
  const [teamId, setTeamId] = useState('');
  const [milestoneId, setMilestoneId] = useState('');
  const [command, setCommand] = useState(null);
  const [notice, setNotice] = useState('');
  const queryKey = ['projects', url, id, 'detail'];
  const detail = useQuery({
    ...queryOptions,
    queryKey,
    queryFn: async ({ signal }) => {
      const [project, teams, milestones] = await Promise.all([
        fetchApi(`${url}${id}/`, { signal }),
        fetchAllResourcePages(`${url}${id}/equipes/`, { page_size: 100 }, { signal }),
        fetchAllResourcePages(`${url}${id}/jalons/`, { page_size: 100 }, { signal }),
      ]);
      return { project, teams, milestones };
    },
  });
  useEffect(() => {
    if (isDenied(detail.error)) { onDenied(detail.error); }
  }, [detail.error, onDenied]);
  const refresh = async () => {
    const result = await detail.refetch({ throwOnError: true });
    await client.invalidateQueries({ queryKey: ['projects', url, id, 'team'] });
    return result.data.project.version;
  };
  const openCommand = target => {
    if (!busy && !detail.isFetching) { setNotice(''); setCommand(target); }
  };
  const success = async result => {
    client.setQueryData(queryKey, previous => ({
      ...previous,
      project: result.id ? result : { ...previous.project, version: result.version },
    }));
    await Promise.all([
      client.invalidateQueries({ queryKey: ['projects', url, id] }),
      client.invalidateQueries({ queryKey: ['projects', url, 'list'] }),
    ]);
    setCommand(null);
    setNotice(result.evaluation?.statut === 'publiee' ? 'Évaluation publiée.' : 'Enregistrement confirmé par le serveur.');
  };
  if (detail.error) {
    return (
      <Alert severity="error">
        Projet indisponible. {apiErrorMessage(detail.error)}
        <Button onClick={() => detail.refetch()}>Réessayer</Button>
        <Button onClick={onBack} disabled={busy}>Retour aux projets</Button>
      </Alert>
    );
  }
  if (!detail.data) { return <Alert severity="info">Chargement du projet…</Alert>; }
  const { project, teams, milestones } = detail.data;
  const team = teams.find(item => item.id === teamId) || teams[0];
  const milestone = milestones.find(item => item.id === milestoneId) || milestones[0];
  const targetTeam = teams.find(item => item.id === command?.teamId);
  const targetMilestone = milestones.find(item => item.id === command?.milestoneId);
  const locked = busy || detail.isFetching;
  const commandAllowed = command && ({
    configure: project.actions.can_manage,
    team: project.actions.can_manage,
    milestone: project.actions.can_manage,
    members: targetTeam?.actions.can_manage,
    delivery: targetTeam?.actions.can_submit && Boolean(targetMilestone),
    evaluation: targetTeam?.actions.can_evaluate && Boolean(targetMilestone),
    publish: targetTeam?.actions.can_evaluate && Boolean(targetMilestone),
  })[command.kind];
  return (
    <Stack spacing={3}>
      <Button sx={{ alignSelf: 'flex-start' }} onClick={onBack} disabled={locked}>Retour aux projets</Button>
      <PageHeader title={project.titre} subtitle={`Projet ${project.mode} · Version ${project.version}`} />
      <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{project.description}</Typography>
      <Typography sx={{ overflowWrap: 'anywhere' }}>{bindingLabel(project.cours)}</Typography>
      <Typography sx={{ overflowWrap: 'anywhere' }}>{competencyLabel(project.competences)}</Typography>
      <Alert severity="info">{rules}</Alert>
      {notice && <Alert severity="success">{notice}</Alert>}
      {detail.isFetching && <Alert severity="info">Actualisation du projet…</Alert>}
      <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap' }}>
        <Button disabled={locked} onClick={() => { setNotice(''); detail.refetch(); client.invalidateQueries({ queryKey: ['projects', url, id, 'team'] }); }}>Actualiser le projet</Button>
        {project.actions.can_manage && (
          <>
            <Button disabled={locked} onClick={() => openCommand({ kind: 'configure' })}>Configurer le projet</Button>
            <Button disabled={locked} onClick={() => openCommand({ kind: 'milestone' })}>Nouveau jalon</Button>
            <Button disabled={locked} onClick={() => openCommand({ kind: 'team' })}>Nouvelle équipe</Button>
          </>
        )}
      </Stack>
      <SISDataTable title="Jalons communs" columns={milestoneColumns} data={milestones} searchable={false} exportable={false} emptyMessage="Aucun jalon défini." />
      <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>
        <Stack spacing={2}>
          <Typography variant="h5" component="h2">Équipes et travaux</Typography>
          {!teams.length && <Alert severity="info">Aucune équipe accessible.</Alert>}
          {team && (
            <>
              <TextField label="Équipe" select value={team.id} disabled={locked} onChange={event => { setTeamId(event.target.value); setNotice(''); }} slotProps={selectProps}>
                {teams.map(item => <option key={item.id} value={item.id}>{item.nom}</option>)}
              </TextField>
              <Typography>Membres actifs : {team.membres.map(member => member.nom).join(', ') || 'Aucun membre actif'}</Typography>
              {team.membres.length === 0 && <Alert severity="warning">Équipe vide : preuves conservées, dépôt et publication indisponibles.</Alert>}
              {team.actions.can_manage && <Button disabled={locked} onClick={() => openCommand({ kind: 'members', teamId: team.id })}>Remplacer les membres actifs</Button>}
              {!milestones.length && <Alert severity="info">Les dépôts et évaluations nécessitent un jalon.</Alert>}
              {milestone && (
                <>
                  <TextField label="Jalon" select value={milestone.id} disabled={locked} onChange={event => { setMilestoneId(event.target.value); setNotice(''); }} slotProps={selectProps}>
                    {milestones.map(item => <option key={item.id} value={item.id}>{item.titre}</option>)}
                  </TextField>
                  <Typography>Échéance : {dateLabel(milestone.echeance)} · Barème : {milestone.bareme}</Typography>
                  <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{milestone.consignes}</Typography>
                  <ProjectTeamPanel
                    key={`${team.id}/${milestone.id}`}
                    url={url}
                    projectId={id}
                    team={team}
                    milestone={milestone}
                    disabled={locked}
                    onCommand={openCommand}
                    onDenied={onDenied}
                    onBusy={onBusy}
                  />
                </>
              )}
            </>
          )}
        </Stack>
      </Paper>
      {command && !commandAllowed && <Alert severity="warning">Cette action n’est plus autorisée. Les capacités du serveur ont changé.</Alert>}
      {commandAllowed && (
        <ProjectCommandDialog
          url={url}
          project={project}
          team={targetTeam}
          milestone={targetMilestone}
          kind={command.kind}
          evaluationId={command.evaluationId}
          onClose={() => setCommand(null)}
          onBusy={onBusy}
          onSuccess={success}
          onReload={refresh}
          onDenied={onDenied}
        />
      )}
    </Stack>
  );
};
ProjectDetail.propTypes = {
  url: PropTypes.string.isRequired,
  id: PropTypes.string.isRequired,
  busy: PropTypes.bool.isRequired,
  onBusy: PropTypes.func.isRequired,
  onBack: PropTypes.func.isRequired,
  onDenied: PropTypes.func.isRequired,
};
export default ProjectDetail;
