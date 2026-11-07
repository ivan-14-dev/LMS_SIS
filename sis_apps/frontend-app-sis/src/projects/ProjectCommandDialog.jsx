import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useMutation } from '@tanstack/react-query';
import {
  Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, Stack, TextField, Typography,
} from '@mui/material';
import { postApi } from '../services/api';
import { apiErrorMessage } from '../services/resources';
import ProjectCandidates from './ProjectCandidates';
import ProjectCourseCandidates from './ProjectCourseCandidates';
import ProjectCompetencyCandidates from './ProjectCompetencyCandidates';
import {
  bindingLabel, competencyLabel, isDenied, milestoneType, projectType, rules, selectProps, teamType,
} from './projectUi';

const titles = {
  create: 'Nouveau projet',
  configure: 'Configurer le projet',
  team: 'Nouvelle équipe',
  members: 'Remplacer les membres actifs',
  milestone: 'Nouveau jalon',
  delivery: 'Déposer un PDF',
  evaluation: 'Brouillon d’évaluation',
  publish: 'Publier l’évaluation',
};
const ProjectCommandDialog = ({
  url, project, team, milestone, evaluationId, kind, onClose, onSuccess, onReload, onDenied, onBusy,
}) => {
  const [version, setVersion] = useState(project?.version);
  const [values, setValues] = useState({
    titre: kind === 'configure' ? project.titre : '',
    description: kind === 'configure' ? project.description : '',
    mode: 'collectif',
    nom: '',
    ordre: '',
    echeance: '',
    bareme: '20',
    consignes: '',
    commentaire: '',
    note_groupe: '',
  });
  const [responsable, setResponsable] = useState(null);
  const [course, setCourse] = useState(null);
  const [courseChanged, setCourseChanged] = useState(false);
  const [choosingCourse, setChoosingCourse] = useState(kind === 'create');
  const [competencies, setCompetencies] = useState([]);
  const [competenciesChanged, setCompetenciesChanged] = useState(false);
  const [choosingCompetencies, setChoosingCompetencies] = useState(false);
  const [competencyReady, setCompetencyReady] = useState(false);
  const [competencyReview, setCompetencyReview] = useState(false);
  const [evaluateurs, setEvaluateurs] = useState([]);
  const [replaceEvaluators, setReplaceEvaluators] = useState(false);
  const [members, setMembers] = useState(
    kind === 'members' ? team.membres.map(member => ({ id: member.membre, nom: member.nom })) : [],
  );
  const [contributions, setContributions] = useState({});
  const [file, setFile] = useState(null);
  const [reloading, setReloading] = useState(false);
  const [reloadError, setReloadError] = useState(null);
  const [conflict, setConflict] = useState(false);
  const sending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  // The dialog owns its destination and version; changing selections cannot retarget an in-flight command.
  const destination = useRef({
    project: project?.id, team: team?.id, milestone: milestone?.id, evaluation: evaluationId,
  }).current;
  const mutation = useMutation({
    retry: false,
    mutationFn: async ({ endpoint, payload, resultKey }) => {
      const result = await postApi(endpoint, payload);
      if (!Number.isInteger(result?.version) || (resultKey ? !result[resultKey]?.id : !result.id)) {
        throw new Error('Réponse de commande invalide. Rechargez le projet avant toute nouvelle tentative.');
      }
      return result;
    },
    onSuccess: result => (mounted.current ? onSuccess(result) : undefined),
    onError: error => {
      if (error?.response?.status === 409) { setConflict(true); }
      if (isDenied(error)) { onDenied(error); }
    },
    onSettled: () => { sending.current = false; onBusy(false); },
  });
  const busy = mutation.isPending || reloading;
  const invalidCompetencies = ['create', 'configure'].includes(kind)
    && (competencyReview || (choosingCompetencies && !competencyReady));
  const chosenCourse = courseChanged ? course : project?.cours;
  const selectedCourse = kind === 'create' ? course : chosenCourse;
  const ownerId = responsable?.id || project?.responsable;
  const reviewCompetencies = () => {
    setChoosingCompetencies(false);
    if (choosingCompetencies || competencies.length || (!competenciesChanged && project?.competences)) {
      setCompetencyReview(true);
    }
  };
  useEffect(() => {
    if (project?.competences?.disponible === false) {
      setCompetencies([]);
      setCompetenciesChanged(false);
      setChoosingCompetencies(false);
      setCompetencyReview(true);
    }
  }, [project?.competences?.disponible]);
  const field = (name, maxLength) => ({
    value: values[name],
    onChange: event => setValues(previous => ({ ...previous, [name]: event.target.value })),
    disabled: busy,
    slotProps: { htmlInput: { maxLength } },
  });
  const submit = event => {
    event.preventDefault();
    if (sending.current || busy || conflict || invalidCompetencies) { return; }
    const projectUrl = `${url}${destination.project}/`;
    const teamUrl = `${projectUrl}equipes/${destination.team}/`;
    let endpoint = url;
    let resultKey;
    let payload;
    switch (kind) {
      case 'create':
        payload = {
          titre: values.titre,
          description: values.description,
          mode: values.mode,
          responsable: responsable.id,
          evaluateurs: evaluateurs.map(user => user.id),
          ...(course ? { cours: course.id } : {}),
          ...(competenciesChanged ? { competences: competencies.map(item => item.code) } : {}),
        };
        break;
      case 'configure':
        endpoint = `${projectUrl}configurer/`;
        payload = {
          version,
          titre: values.titre,
          description: values.description,
          ...(responsable ? { responsable: responsable.id } : {}),
          ...(replaceEvaluators ? { evaluateurs: evaluateurs.map(user => user.id) } : {}),
          ...(courseChanged ? { cours: course?.id || null } : {}),
          ...(competenciesChanged ? { competences: competencies.map(item => item.code) } : {}),
        };
        break;
      case 'team':
      case 'members':
        endpoint = kind === 'team' ? `${projectUrl}equipes/` : `${teamUrl}membres/`;
        resultKey = 'equipe';
        payload = { version, membres: members.map(user => user.id), ...(kind === 'team' ? { nom: values.nom } : {}) };
        break;
      case 'milestone':
        endpoint = `${projectUrl}jalons/`;
        resultKey = 'jalon';
        payload = {
          version,
          titre: values.titre,
          consignes: values.consignes,
          ordre: Number(values.ordre),
          echeance: new Date(values.echeance).toISOString(),
          bareme: values.bareme,
        };
        break;
      case 'delivery':
        endpoint = `${teamUrl}livrables/`;
        resultKey = 'livrable';
        payload = new FormData();
        payload.append('version', version);
        payload.append('jalon', destination.milestone);
        payload.append('fichier', file);
        payload.append('commentaire', values.commentaire);
        break;
      case 'evaluation':
        endpoint = `${teamUrl}evaluations/`;
        resultKey = 'evaluation';
        payload = {
          version,
          jalon: destination.milestone,
          note_groupe: values.note_groupe,
          commentaire: values.commentaire,
          contributions: team.membres.filter(member => contributions[member.membre]?.note !== undefined
            && contributions[member.membre].note !== '').map(member => ({
            membre: member.membre,
            note: contributions[member.membre].note,
            commentaire: contributions[member.membre].commentaire || '',
          })),
        };
        break;
      case 'publish':
        endpoint = `${teamUrl}evaluations/${destination.evaluation}/publier/`;
        resultKey = 'evaluation';
        payload = { version };
        break;
      default: return;
    }
    sending.current = true;
    onBusy(true);
    mutation.mutate({ endpoint, payload, resultKey });
  };
  const reload = async () => {
    setReloading(true);
    onBusy(true);
    setReloadError(null);
    try {
      const currentVersion = await onReload();
      setVersion(currentVersion);
      setConflict(false);
      mutation.reset();
    } catch (error) {
      setReloadError(error);
      if (isDenied(error)) { onDenied(error); }
    } finally {
      setReloading(false);
      onBusy(false);
    }
  };
  const individual = (project?.mode || values.mode) === 'individuel';
  const invalidMembers = ['team', 'members'].includes(kind)
    && ((individual && members.length > 1) || (kind === 'team' && members.length === 0));
  const updateContribution = (id, name, value) => setContributions(previous => ({
    ...previous, [id]: { ...previous[id], [name]: value },
  }));
  const courseChangeLabel = course ? `Nouveau choix : ${course.nom}` : 'Retrait du rattachement à confirmer.';
  return (
    <Dialog open fullWidth maxWidth="sm" onClose={busy ? undefined : onClose} disableEscapeKeyDown={busy}>
      <Box component="form" onSubmit={submit}>
        <DialogTitle>{titles[kind]}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {team && <Typography>Équipe : {team.nom}{milestone ? ` · Jalon : ${milestone.titre}` : ''}</Typography>}
            {['create', 'configure'].includes(kind) && (
              <>
                <TextField label="Titre du projet" required {...field('titre', 200)} />
                <TextField label="Description" multiline minRows={3} {...field('description', 10000)} />
                {kind === 'create' && (
                  <TextField label="Mode du projet" select {...field('mode')} slotProps={selectProps}>
                    <option value="collectif">Collectif</option><option value="individuel">Individuel</option>
                  </TextField>
                )}
                <ProjectCandidates
                  url={url}
                  projectId={project?.id}
                  type="responsable"
                  label={kind === 'create' ? 'Responsable' : 'Nouveau responsable (facultatif)'}
                  value={responsable}
                  onChange={user => {
                    setResponsable(user);
                    reviewCompetencies();
                    if (kind === 'create') { setEvaluateurs([]); }
                  }}
                  onDenied={onDenied}
                  disabled={busy}
                  required={kind === 'create'}
                />
                {kind === 'configure' && (
                  <>
                    <Typography>{courseChanged ? courseChangeLabel : bindingLabel(project.cours)}</Typography>
                    <Stack direction="row" spacing={1}>
                      <Button disabled={busy} onClick={() => setChoosingCourse(true)}>Choisir un cours</Button>
                      <Button
                        disabled={busy}
                        onClick={() => {
                          setCourse(null);
                          setCourseChanged(true);
                          setChoosingCourse(false);
                          reviewCompetencies();
                        }}
                      >
                        Retirer le rattachement
                      </Button>
                    </Stack>
                  </>
                )}
                {choosingCourse && (
                  <ProjectCourseCandidates
                    key={`course-${responsable?.id || project?.responsable || 'no-owner'}`}
                    url={url}
                    projectId={project?.id}
                    ownerId={responsable?.id || project?.responsable}
                    value={course}
                    onChange={selected => { setCourse(selected); setCourseChanged(true); reviewCompetencies(); }}
                    onDenied={onDenied}
                    disabled={busy}
                  />
                )}
                <Typography sx={{ overflowWrap: 'anywhere' }}>
                  {competenciesChanged
                    ? competencyLabel(competencies.length ? { disponible: true, criteria: competencies } : null)
                    : competencyLabel(project?.competences)}
                </Typography>
                {competencyReview && (
                  <Alert severity="warning">
                    Contexte modifié ou indisponible : les compétences ne sont pas réassociées automatiquement.
                    Recommencez leur sélection ou retirez-les explicitement avant de confirmer.
                  </Alert>
                )}
                <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap' }}>
                  <Button
                    disabled={busy || !selectedCourse?.id || !ownerId}
                    onClick={() => {
                      setCompetencies([]);
                      setCompetenciesChanged(true);
                      if (!choosingCompetencies) { setCompetencyReady(false); }
                      setChoosingCompetencies(true);
                      setCompetencyReview(false);
                    }}
                  >
                    Nouvelle sélection des compétences visées
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() => {
                      setCompetencies([]);
                      setCompetenciesChanged(true);
                      setChoosingCompetencies(false);
                      setCompetencyReview(false);
                    }}
                  >
                    Retirer les compétences visées
                  </Button>
                </Stack>
                {choosingCompetencies && selectedCourse?.id && ownerId && (
                  <ProjectCompetencyCandidates
                    key={`competencies-${selectedCourse.id}-${ownerId}`}
                    url={url}
                    projectId={project?.id}
                    courseId={selectedCourse.id}
                    ownerId={ownerId}
                    value={competencies}
                    onChange={setCompetencies}
                    onDenied={onDenied}
                    onReadyChange={setCompetencyReady}
                    disabled={busy}
                  />
                )}
                <Alert severity="info">
                  La nouvelle sélection remplace le choix précédent ; aucun choix conserve les compétences existantes.
                  Une sélection vide les retire. Seuls les critères de l’offre liée sont proposés, sans acquisition
                  ni note officielle. Toute modification de cette offre impose une nouvelle sélection ou un retrait.
                </Alert>
                <Alert severity="info">
                  Le serveur revérifie les accès au cours et la compatibilité du responsable à chaque configuration.
                  Un cours révoqué doit être remplacé ou explicitement retiré pour configurer le projet.
                  Les équipes, contributions et preuves restent inchangées.
                </Alert>
                {kind === 'configure' && (
                  <FormControlLabel
                    control={(
                      <Checkbox
                        checked={replaceEvaluators}
                        onChange={event => setReplaceEvaluators(event.target.checked)}
                        disabled={busy}
                      />
                    )}
                    label="Remplacer la liste des évaluateurs (sinon conservée)"
                  />
                )}
                {(kind === 'create' || replaceEvaluators) && (
                  <ProjectCandidates
                    key={kind === 'create' ? responsable?.id || 'no-owner' : project.id}
                    url={url}
                    projectId={project?.id}
                    type="evaluateur"
                    label="Évaluateurs"
                    ownerId={kind === 'create' ? responsable?.id : undefined}
                    multiple
                    value={evaluateurs}
                    onChange={setEvaluateurs}
                    onDenied={onDenied}
                    disabled={busy || (kind === 'create' && !responsable)}
                  />
                )}
                <Alert severity="info">{rules} Le mode ne peut plus être modifié après création.</Alert>
              </>
            )}
            {['team', 'members'].includes(kind) && (
              <>
                {kind === 'team' && <TextField label="Nom de l’équipe" required {...field('nom', 120)} />}
                <ProjectCandidates
                  url={url}
                  projectId={project.id}
                  type="membre"
                  label="Membres actifs"
                  multiple
                  value={members}
                  onChange={setMembers}
                  onDenied={onDenied}
                  disabled={busy}
                  required={kind === 'team'}
                />
                <Alert severity="info">{rules} Le remplacement retire immédiatement l’accès des membres non retenus.</Alert>
                {invalidMembers && <Alert severity="warning">Choisissez {individual ? 'une seule personne' : 'au moins une personne'} pour créer l’équipe.</Alert>}
              </>
            )}
            {kind === 'milestone' && (
              <>
                <TextField label="Titre du jalon" required {...field('titre', 200)} />
                <TextField label="Consignes" multiline {...field('consignes', 10000)} />
                <TextField label="Ordre" type="number" required {...field('ordre')} slotProps={{ htmlInput: { min: 1, max: 100000, step: 1 } }} />
                <TextField label="Échéance (heure locale)" type="datetime-local" required {...field('echeance')} slotProps={{ inputLabel: { shrink: true } }} />
                <TextField label="Barème" type="number" required {...field('bareme')} slotProps={{ htmlInput: { min: 0.01, max: 10000, step: 0.01 } }} />
                <Alert severity="info">Le jalon, son échéance et son barème sont communs aux équipes et ne seront plus modifiables.</Alert>
              </>
            )}
            {kind === 'delivery' && (
              <>
                <Alert severity="info">PDF privé, 25 Mio maximum par défaut. Chaque dépôt conserve les révisions précédentes. Les retards restent acceptés et signalés.</Alert>
                <input aria-label="Fichier PDF" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={event => setFile(event.target.files[0] || null)} />
                <TextField label="Commentaire du dépôt" multiline {...field('commentaire', 4000)} />
              </>
            )}
            {kind === 'evaluation' && (
              <>
                <Alert severity="info">Brouillon non publié · barème {milestone.bareme}. La publication explicite exige une contribution notée et commentée pour chaque membre actuel. Pour corriger une évaluation, créez un nouveau brouillon.</Alert>
                <TextField label="Note du groupe" type="number" required {...field('note_groupe')} slotProps={{ htmlInput: { min: 0, max: Number(milestone.bareme), step: 0.01 } }} />
                <TextField label="Commentaire du groupe" multiline required {...field('commentaire', 10000)} />
                {team.membres.map(member => (
                  <Box
                    key={member.membre}
                    component="fieldset"
                    sx={{
                      border: 1, borderColor: 'divider', borderRadius: 1, p: 2,
                    }}
                  >
                    <legend>{member.nom}</legend>
                    <Stack spacing={2}>
                      <TextField
                        label={`Note de ${member.nom}`}
                        type="number"
                        disabled={busy}
                        value={contributions[member.membre]?.note || ''}
                        onChange={event => updateContribution(member.membre, 'note', event.target.value)}
                        slotProps={{ htmlInput: { min: 0, max: Number(milestone.bareme), step: 0.01 } }}
                      />
                      <TextField
                        label={`Contribution de ${member.nom}`}
                        multiline
                        disabled={busy}
                        required={Boolean(contributions[member.membre]?.note)}
                        value={contributions[member.membre]?.commentaire || ''}
                        onChange={event => updateContribution(member.membre, 'commentaire', event.target.value)}
                        slotProps={{ htmlInput: { maxLength: 4000 } }}
                      />
                    </Stack>
                  </Box>
                ))}
              </>
            )}
            {kind === 'publish' && <Alert severity="warning">Confirmez la publication de cette révision. Elle deviendra visible aux membres ; chacun ne verra que sa contribution personnelle. Aucune note officielle ne sera créée.</Alert>}
            {busy && <Alert severity="info">Commande en cours. Ne quittez pas cette fenêtre.</Alert>}
            {(mutation.error || reloadError) && (
              <Alert severity="error">
                {apiErrorMessage(reloadError || mutation.error)}
                {conflict && ' Conflit de version : vos saisies sont conservées. Rechargez le projet, vérifiez les données puis confirmez à nouveau. Aucun renvoi automatique.'}
                {project && (
                  <Button disabled={busy} onClick={reload}>Recharger le projet sans effacer les saisies</Button>
                )}
              </Alert>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={busy}>Annuler</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={busy || conflict || invalidMembers
              || invalidCompetencies
              || (kind === 'create' && !responsable) || (kind === 'delivery' && !file)}
          >
            {kind === 'publish' ? 'Confirmer la publication' : 'Enregistrer'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};
ProjectCommandDialog.propTypes = {
  url: PropTypes.string.isRequired,
  project: projectType,
  team: teamType,
  milestone: milestoneType,
  evaluationId: PropTypes.string,
  kind: PropTypes.oneOf(Object.keys(titles)).isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
  onReload: PropTypes.func,
  onDenied: PropTypes.func.isRequired,
  onBusy: PropTypes.func.isRequired,
};
export default ProjectCommandDialog;
