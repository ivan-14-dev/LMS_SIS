import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useOutletContext } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Tabs,
  Tab,
  Chip,
  Alert,
  AlertTitle,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  LinearProgress,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  Switch,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Sync as SyncIcon,
  Check as CheckIcon,
  Error as ErrorIcon,
  Person as PersonIcon,
  School as SchoolIcon,
  Assignment as AssignmentIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  PlayArrow as PlayArrowIcon,
  Schedule as ScheduleIcon,
  CloudDone as CloudDoneIcon,
  CloudOff as CloudOffIcon,
  Publish as PublishIcon,
  InfoOutlined as InfoIcon,
} from '@mui/icons-material';
import { PageHeader, StatusBadge } from '../../components/common';
import CoursePublicationDialog from './CoursePublicationDialog';
import UserSynchronizationDialog from './UserSynchronizationDialog';
import {
  getIntegrationApiUrl,
  requestIntegrationOutboxProcessing,
  useIntegrationCourseMappings,
  useIntegrationHealth,
  useIntegrationOutboxEvents,
  useIntegrationStats,
  useIntegrationUserCandidates,
  useIntegrationUserMappings,
} from '../../services/api';

const StatCard = ({
  title, value = 0, icon, color = 'primary', subtitle = null,
}) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box>
          <Typography color="textSecondary" variant="body2" gutterBottom>
            {title}
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 600, color: `${color}.main` }}>
            {value}
          </Typography>
          {subtitle && (
            <Typography variant="caption" color="textSecondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        <Box sx={{
          p: 1.5,
          borderRadius: 2,
          bgcolor: `${color}.lighter`,
          color: `${color}.main`,
        }}
        >
          {icon}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

StatCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  icon: PropTypes.node.isRequired,
  color: PropTypes.string,
  subtitle: PropTypes.string,
};

StatCard.defaultProps = {
  value: 0,
  color: 'primary',
  subtitle: null,
};

const ConnectionStatus = ({ status, isRefreshing, onRefresh }) => {
  const isConnected = status?.connected;

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2,
        }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {isConnected ? (
              <CloudDoneIcon sx={{ fontSize: 48, color: 'success.main' }} />
            ) : (
              <CloudOffIcon sx={{ fontSize: 48, color: 'error.main' }} />
            )}
            <Box>
              <Typography variant="h6">
                Connexion Open edX LMS
              </Typography>
              <Typography variant="body2" color="textSecondary">
                {status?.lms_url || 'Non configuré'}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Chip
              icon={isConnected ? <CheckIcon /> : <ErrorIcon />}
              label={isConnected ? 'Contrat disponible' : 'LMS indisponible'}
              color={isConnected ? 'success' : 'error'}
            />
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              size="small"
              disabled={isRefreshing}
              onClick={onRefresh}
            >
              {isRefreshing ? 'Vérification…' : 'Vérifier'}
            </Button>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {status?.configured === false && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Aucun raccordement LMS configuré. L’authentification locale du SIS ne donne pas accès à Open edX.
            {status.missing_configuration?.length > 0
              && ` Paramètres manquants : ${status.missing_configuration.join(', ')}.`}
          </Alert>
        )}
        {status?.configured === true && !isConnected && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Le contrat sis-provisioning et ses permissions ne sont pas confirmés sur LMS et Studio.
            Un heartbeat seul ne valide pas les identités, cours ou inscriptions.
          </Alert>
        )}
        <Alert severity="info" role="note" sx={{ mb: 2 }}>
          Les webhooks, propositions de notes et fournisseurs pédagogiques nécessitent une qualification distincte.
          Les notes LMS restent des propositions jusqu’à validation humaine dans le SIS.
        </Alert>

        <Grid container spacing={3}>
          <Grid size={{
            xs: 12,
            md: 3,
          }}
          >
            <Typography variant="body2" color="textSecondary">Version LMS</Typography>
            <Typography variant="body1" fontWeight={500}>{status?.version || '-'}</Typography>
          </Grid>
          <Grid size={{
            xs: 12,
            md: 3,
          }}
          >
            <Typography variant="body2" color="textSecondary">OAuth</Typography>
            <Chip
              size="small"
              label={status?.oauth_status || 'N/A'}
              color={status?.oauth_status === 'valid' ? 'success' : 'warning'}
            />
          </Grid>
          <Grid size={{
            xs: 12,
            md: 3,
          }}
          >
            <Typography variant="body2" color="textSecondary">Webhooks</Typography>
            <Chip
              size="small"
              label={status?.webhook_status === 'unverified' ? 'Non vérifié' : status?.webhook_status || 'N/A'}
              color={status?.webhook_status === 'active' ? 'success' : 'warning'}
            />
          </Grid>
          <Grid size={{
            xs: 12,
            md: 3,
          }}
          >
            <Typography variant="body2" color="textSecondary">Dernière vérification</Typography>
            <Typography variant="body1">
              {status?.last_check ? new Date(status.last_check).toLocaleString('fr-FR') : '-'}
            </Typography>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

ConnectionStatus.propTypes = {
  status: PropTypes.shape({
    connected: PropTypes.bool,
    configured: PropTypes.bool,
    missing_configuration: PropTypes.arrayOf(PropTypes.string),
    lms_url: PropTypes.string,
    version: PropTypes.string,
    oauth_status: PropTypes.string,
    webhook_status: PropTypes.string,
    last_check: PropTypes.string,
  }).isRequired,
  isRefreshing: PropTypes.bool.isRequired,
  onRefresh: PropTypes.func.isRequired,
};

const OutboxStatusCard = ({ outbox = {} }) => {
  const total = Object.values(outbox || {}).reduce((a, b) => a + b, 0);
  const pendingPercent = outbox?.pending ? (outbox.pending / total) * 100 : 0;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>File d’attente (Outbox)</Typography>
        <Box sx={{ mb: 2 }}>
          <LinearProgress
            variant="determinate"
            value={100 - pendingPercent}
            sx={{ height: 8, borderRadius: 4 }}
          />
        </Box>
        <Grid container spacing={2}>
          <Grid size={{
            xs: 4,
          }}
          >
            <Box sx={{ textAlign: 'center' }}>
              <Chip label={outbox?.pending || 0} color="warning" size="small" />
              <Typography variant="caption" display="block">En attente</Typography>
            </Box>
          </Grid>
          <Grid size={{
            xs: 4,
          }}
          >
            <Box sx={{ textAlign: 'center' }}>
              <Chip label={outbox?.processing || 0} color="info" size="small" />
              <Typography variant="caption" display="block">En cours</Typography>
            </Box>
          </Grid>
          <Grid size={{
            xs: 4,
          }}
          >
            <Box sx={{ textAlign: 'center' }}>
              <Chip label={(outbox?.failed || 0) + (outbox?.dead || 0)} color="error" size="small" />
              <Typography variant="caption" display="block">Échecs</Typography>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

OutboxStatusCard.propTypes = {
  outbox: PropTypes.shape({
    pending: PropTypes.number,
    processing: PropTypes.number,
    failed: PropTypes.number,
    dead: PropTypes.number,
  }),
};

OutboxStatusCard.defaultProps = {
  outbox: {},
};

const UserMappingsTab = ({
  mappings, candidates, canSynchronize, onSynchronize,
}) => {
  const actionLabel = candidates ? 'Associer cette identité LMS' : 'Synchroniser l’identité LMS';
  return (
    <TableContainer component={Paper} sx={{ mt: 2 }}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Utilisateur SIS</TableCell>
            <TableCell>Username EdX</TableCell>
            <TableCell>ID EdX</TableCell>
            <TableCell>Dernière sync</TableCell>
            <TableCell>Statut</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {mappings.map((mapping) => (
            <TableRow key={mapping.user_sis}>
              <TableCell>
                {mapping.user_sis_name || mapping.user_sis_username || mapping.user_sis}
              </TableCell>
              <TableCell>
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                  {mapping.username_edx}
                </Typography>
              </TableCell>
              <TableCell>{mapping.user_id_edx || '-'}</TableCell>
              <TableCell>
                {mapping.date_sync ? new Date(mapping.date_sync).toLocaleString('fr-FR') : 'Jamais'}
              </TableCell>
              <TableCell>
                <StatusBadge value={mapping.actif ? 'actif' : 'inactif'} />
              </TableCell>
              <TableCell align="right">
                <Tooltip title={mapping.actif ? actionLabel : 'Association LMS désactivée'}>
                  <span>
                    <IconButton
                      size="small"
                      color="primary"
                      aria-label={`${candidates ? 'Associer' : 'Synchroniser'} l’identité LMS de ${mapping.user_sis_name || mapping.user_sis_username || mapping.user_sis} (${mapping.username_edx})`}
                      disabled={!canSynchronize || !mapping.actif}
                      onClick={() => onSynchronize(mapping)}
                    >
                      <SyncIcon />
                    </IconButton>
                  </span>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

UserMappingsTab.propTypes = {
  candidates: PropTypes.bool.isRequired,
  canSynchronize: PropTypes.bool.isRequired,
  onSynchronize: PropTypes.func.isRequired,
  mappings: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number,
    user_sis: PropTypes.number,
    user_sis_name: PropTypes.string,
    user_sis_username: PropTypes.string,
    username_edx: PropTypes.string.isRequired,
    user_id_edx: PropTypes.number,
    date_sync: PropTypes.string,
    actif: PropTypes.bool.isRequired,
  })).isRequired,
};

const CourseMappingsTab = ({ mappings, canPublish, onPublish }) => (
  <TableContainer component={Paper} sx={{ mt: 2 }}>
    <Table>
      <TableHead>
        <TableRow>
          <TableCell>ECUE</TableCell>
          <TableCell>Course ID</TableCell>
          <TableCell>Nom dans LMS</TableCell>
          <TableCell>Statut</TableCell>
          <TableCell align="right">Actions</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {mappings.map((mapping) => (
          <TableRow key={mapping.id}>
            <TableCell>
              {mapping.ecue_nom || mapping.matiere_nom || mapping.ecue || mapping.matiere}
            </TableCell>
            <TableCell>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                {mapping.course_id}
              </Typography>
            </TableCell>
            <TableCell>{mapping.course_name}</TableCell>
            <TableCell>
              <StatusBadge value={mapping.actif ? 'actif' : 'inactif'} />
            </TableCell>
            <TableCell align="right">
              <Tooltip title="Ouvrir dans LMS">
                <span>
                  <IconButton size="small" color="primary" disabled>
                    <SchoolIcon />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title="Synchroniser inscriptions">
                <span>
                  <IconButton size="small" color="primary" disabled>
                    <SyncIcon />
                  </IconButton>
                </span>
              </Tooltip>
              {canPublish && (
                <Tooltip title={mapping.actif ? 'Examiner et publier le cours' : 'Association de cours désactivée'}>
                  <span>
                    <IconButton
                      size="small"
                      color="primary"
                      aria-label={`Examiner et publier ${mapping.course_name}`}
                      disabled={!mapping.actif}
                      onClick={() => onPublish(mapping)}
                    >
                      <PublishIcon />
                    </IconButton>
                  </span>
                </Tooltip>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </TableContainer>
);

CourseMappingsTab.propTypes = {
  canPublish: PropTypes.bool.isRequired,
  onPublish: PropTypes.func.isRequired,
  mappings: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    ecue: PropTypes.number,
    ecue_nom: PropTypes.string,
    matiere: PropTypes.number,
    matiere_nom: PropTypes.string,
    course_id: PropTypes.string.isRequired,
    course_name: PropTypes.string.isRequired,
    actif: PropTypes.bool.isRequired,
  })).isRequired,
};

const OutboxEventsTab = ({ events, onDetails }) => (
  <TableContainer component={Paper} sx={{ mt: 2 }}>
    <Table>
      <TableHead>
        <TableRow>
          <TableCell>Type</TableCell>
          <TableCell>Aggregate</TableCell>
          <TableCell>ID</TableCell>
          <TableCell>Statut</TableCell>
          <TableCell>Tentatives</TableCell>
          <TableCell>Créé</TableCell>
          <TableCell>Erreur</TableCell>
          <TableCell align="right">Actions</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {events.map((event) => (
          <TableRow key={event.id}>
            <TableCell>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {event.event_type}
              </Typography>
            </TableCell>
            <TableCell>{event.aggregate_type}</TableCell>
            <TableCell>{event.aggregate_id}</TableCell>
            <TableCell>
              <StatusBadge value={event.statut} />
            </TableCell>
            <TableCell>{event.nb_tentatives}</TableCell>
            <TableCell>
              {new Date(event.created_at).toLocaleString('fr-FR')}
            </TableCell>
            <TableCell>
              <Typography variant="body2" color="error" sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {event.erreur || '-'}
              </Typography>
            </TableCell>
            <TableCell align="right">
              <Tooltip title="Voir les détails">
                <IconButton
                  size="small"
                  color="primary"
                  aria-label={`Voir les détails de l’événement ${event.id}`}
                  onClick={() => onDetails(event)}
                >
                  <InfoIcon />
                </IconButton>
              </Tooltip>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </TableContainer>
);

OutboxEventsTab.propTypes = {
  onDetails: PropTypes.func.isRequired,
  events: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    event_type: PropTypes.string.isRequired,
    aggregate_type: PropTypes.string.isRequired,
    aggregate_id: PropTypes.string.isRequired,
    statut: PropTypes.string.isRequired,
    nb_tentatives: PropTypes.number.isRequired,
    created_at: PropTypes.string.isRequired,
    erreur: PropTypes.string,
  })).isRequired,
};

const PageNavigation = ({
  count, hasNext, hasPrevious, page, onPageChange,
}) => (count > 0 || hasNext || hasPrevious || page > 1) && (
  <Box sx={{
    alignItems: 'center', display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 2, flexWrap: 'wrap',
  }}
  >
    <Typography variant="body2" color="textSecondary">
      {count}
      {' '}
      résultat(s) — page
      {' '}
      {page}
    </Typography>
    {(hasNext || hasPrevious || page > 1) && (
    <Button
      size="small"
      disabled={!hasPrevious}
      onClick={() => onPageChange(page - 1)}
    >
      Précédent
    </Button>
    )}
    {(hasNext || hasPrevious || page > 1) && (
    <Button
      size="small"
      disabled={!hasNext}
      onClick={() => onPageChange(page + 1)}
    >
      Suivant
    </Button>
    )}
  </Box>
);

PageNavigation.propTypes = {
  count: PropTypes.number.isRequired,
  hasNext: PropTypes.bool.isRequired,
  hasPrevious: PropTypes.bool.isRequired,
  page: PropTypes.number.isRequired,
  onPageChange: PropTypes.func.isRequired,
};

const IntegrationLMSPage = () => {
  const { profile } = useOutletContext() || {};
  const canPublish = profile?.is_staff === true;
  const integrationUrl = getIntegrationApiUrl();
  const [publication, setPublication] = useState(null);
  const [tabValue, setTabValue] = useState(0);
  const [userPagination, setUserPagination] = useState({ integrationUrl, page: 1 });
  const userPage = userPagination.integrationUrl === integrationUrl ? userPagination.page : 1;
  const [candidatePagination, setCandidatePagination] = useState({ integrationUrl, page: 1 });
  const candidatePage = candidatePagination.integrationUrl === integrationUrl ? candidatePagination.page : 1;
  const [userView, setUserView] = useState(null);
  const candidates = canPublish && userView === integrationUrl;
  const [userPageNotice, setUserPageNotice] = useState(null);
  const [userSynchronization, setUserSynchronization] = useState(null);
  const [coursePage, setCoursePage] = useState(1);
  const [outboxPage, setOutboxPage] = useState(1);
  const [failuresOnly, setFailuresOnly] = useState(false);
  const [outboxDetails, setOutboxDetails] = useState(null);
  const [outboxAction, setOutboxAction] = useState(null);
  const outboxRequest = useRef(false);
  useEffect(() => {
    setUserPagination({ integrationUrl, page: 1 });
    setCandidatePagination({ integrationUrl, page: 1 });
    setUserView(null);
    setUserPageNotice(null);
    setUserSynchronization(null);
  }, [integrationUrl]);
  const healthQuery = useIntegrationHealth();
  const statsQuery = useIntegrationStats();
  const usersQuery = useIntegrationUserMappings(userPage, tabValue === 0 && !candidates);
  const candidatesQuery = useIntegrationUserCandidates(candidatePage, canPublish && tabValue === 0 && candidates);
  const coursesQuery = useIntegrationCourseMappings(coursePage);
  const outboxQuery = useIntegrationOutboxEvents(outboxPage, failuresOnly);

  const integrationStatus = healthQuery.data || {};
  const syncStats = statsQuery.data || {};
  const userMappings = usersQuery.data?.results || [];
  const userCandidates = canPublish ? candidatesQuery.data?.results || [] : [];
  const userListQuery = candidates ? candidatesQuery : usersQuery;
  const userListPage = candidates ? candidatePage : userPage;
  const userList = candidates ? userCandidates : userMappings;
  const courseMappings = coursesQuery.data?.results || [];
  const outboxEvents = outboxQuery.data?.results || [];
  const queries = [healthQuery, statsQuery, coursesQuery, outboxQuery];
  if (tabValue === 0) { queries.push(userListQuery); }
  const isLoading = queries.some(query => query.isLoading);
  const isRefreshing = queries.some(query => query.isFetching);
  const hasError = queries.some(query => query.isError);

  const refresh = () => Promise.all([
    ...queries.filter(query => query !== userListQuery).map(query => query.refetch()),
    usersQuery.invalidatePages(),
  ]);
  const currentOutboxAction = outboxAction?.integrationUrl === integrationUrl ? outboxAction : null;
  const currentOutboxDetails = outboxDetails?.integrationUrl === integrationUrl ? outboxDetails.event : null;
  const selectedUserMapping = userSynchronization?.integrationUrl === integrationUrl
    ? userSynchronization.mapping : null;
  const currentUserMapping = userMappings.find(mapping => (
    mapping.user_sis === selectedUserMapping?.user_sis
    || (selectedUserMapping?.id != null && mapping.id === selectedUserMapping.id)
  )) || userCandidates.find(mapping => mapping.user_sis === selectedUserMapping?.user_sis);
  // Updating date_sync can move the selected identity to another API page.
  const canSynchronizeUser = canPublish && !userListQuery.isError && Boolean(selectedUserMapping?.actif)
    && (!currentUserMapping || (currentUserMapping.actif
      && currentUserMapping.user_sis === selectedUserMapping.user_sis
      && currentUserMapping.username_edx === selectedUserMapping.username_edx));
  const refreshUserMappings = async (requestUrl) => {
    if (getIntegrationApiUrl() === requestUrl) {
      await Promise.allSettled([usersQuery.invalidatePages(), statsQuery.refetch()]);
    }
  };
  const changeUserPage = (page) => {
    setUserPageNotice(null);
    if (candidates) { setCandidatePagination({ integrationUrl, page }); } else {
      setUserPagination({ integrationUrl, page });
    }
  };
  const userListErrorStatus = userListQuery.error?.response?.status;
  const userListErrorDetail = userListQuery.error?.response?.data?.detail
    || userListQuery.error?.response?.data?.error || userListQuery.error?.message;
  useEffect(() => {
    if (tabValue !== 0 || userListPage <= 1 || userListQuery.isFetching) { return; }
    const missingPage = userListQuery.isError && userListErrorStatus === 404;
    const emptyPage = !userListQuery.isError && userListQuery.data?.results?.length === 0;
    if (!missingPage && !emptyPage) { return; }
    setUserPageNotice({
      integrationUrl,
      candidates,
      message: `La page ${userListPage} n’existe plus${missingPage ? ' (404)' : ''}. Retour à la première page.`,
    });
    if (candidates) { setCandidatePagination({ integrationUrl, page: 1 }); } else {
      setUserPagination({ integrationUrl, page: 1 });
    }
  }, [
    candidates, integrationUrl, tabValue, userListPage, userListErrorStatus,
    userListQuery.isError, userListQuery.isFetching, userListQuery.data,
  ]);

  const processOutbox = async () => {
    if (!canPublish || outboxRequest.current) { return; }
    outboxRequest.current = true;
    setOutboxAction({ integrationUrl, pending: true });
    try {
      const result = await requestIntegrationOutboxProcessing(integrationUrl);
      setOutboxAction({
        integrationUrl,
        message: `Traitement demandé pour cet établissement (tâche ${result.task_id}). `
          + 'La mise en file est confirmée, pas la synchronisation. Actualisez pour suivre les événements.',
      });
    } catch (error) {
      const detail = error.response?.data?.error || error.response?.data?.detail;
      setOutboxAction({
        integrationUrl,
        error: true,
        message: typeof detail === 'string' ? detail
          : error.message || 'La mise en file n’est pas confirmée. Vérifiez vos droits et réessayez plus tard.',
      });
    } finally {
      outboxRequest.current = false;
      if (getIntegrationApiUrl() === integrationUrl) {
        await Promise.allSettled([outboxQuery.refetch(), statsQuery.refetch()]);
      }
    }
  };

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  return (
    <Box>
      <PageHeader
        title="Intégration LMS"
        subtitle="Synchronisation avec Open edX Learning Management System"
        actions={[
          {
            label: 'Actualiser',
            icon: <RefreshIcon />,
            variant: 'outlined',
            onClick: refresh,
          },
        ]}
      />

      {hasError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Impossible de charger la supervision Open edX. Vérifiez vos droits administrateur et la configuration API.
        </Alert>
      )}
      {isLoading && <CircularProgress sx={{ mb: 3 }} />}

      {/* Connection Status */}
      <ConnectionStatus
        status={integrationStatus}
        isRefreshing={isRefreshing}
        onRefresh={refresh}
      />

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{
          xs: 12,
          sm: 6,
          md: 3,
        }}
        >
          <StatCard
            title="Utilisateurs mappés"
            value={syncStats.users_mapped?.toLocaleString()}
            icon={<PersonIcon />}
            color="primary"
            subtitle="Associations SIS ↔ LMS"
          />
        </Grid>
        <Grid size={{
          xs: 12,
          sm: 6,
          md: 3,
        }}
        >
          <StatCard
            title="Cours mappés"
            value={syncStats.courses_mapped}
            icon={<SchoolIcon />}
            color="success"
            subtitle="ECUE → Cours LMS"
          />
        </Grid>
        <Grid size={{
          xs: 12,
          sm: 6,
          md: 3,
        }}
        >
          <StatCard
            title="Inscriptions actives"
            value={syncStats.enrollments_active?.toLocaleString()}
            icon={<AssignmentIcon />}
            color="info"
            subtitle="Étudiants inscrits aux cours"
          />
        </Grid>
        <Grid size={{
          xs: 12,
          sm: 6,
          md: 3,
        }}
        >
          <OutboxStatusCard outbox={syncStats.outbox} />
        </Grid>
      </Grid>

      {/* Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab icon={<PersonIcon />} label="Utilisateurs" iconPosition="start" />
            <Tab icon={<SchoolIcon />} label="Cours" iconPosition="start" />
            <Tab icon={<ScheduleIcon />} label="File d'attente" iconPosition="start" />
            <Tab icon={<SettingsIcon />} label="Configuration" iconPosition="start" />
          </Tabs>
        </Box>
        <CardContent>
          {tabValue === 0 && (
            <>
              <Box sx={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2,
              }}
              >
                <Typography variant="h6">
                  {candidates ? 'Utilisateurs SIS à associer au LMS' : 'Mappings Utilisateurs SIS ↔ LMS'}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {canPublish && (
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => {
                        setUserView(candidates ? null : integrationUrl);
                        setUserPageNotice(null);
                      }}
                    >
                      {candidates ? 'Voir les associations' : 'Associer un utilisateur'}
                    </Button>
                  )}
                  <Button variant="outlined" startIcon={<SyncIcon />} size="small" disabled>
                    Synchroniser tous
                  </Button>
                </Box>
              </Box>
              {candidates && (
                <Typography variant="body2" color="textSecondary">
                  Utilisateurs SIS actifs sans aucune association LMS, même désactivée.
                  Choisissez une identité pour examiner et confirmer sa première association, sans attribution d’accès.
                </Typography>
              )}
              {userPageNotice?.integrationUrl === integrationUrl && userPageNotice.candidates === candidates && (
                <Alert severity="warning" sx={{ mt: 2 }}>{userPageNotice.message}</Alert>
              )}
              {userListQuery.isError && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  Impossible de charger {candidates ? 'les utilisateurs à associer' : 'les associations LMS'}.
                  {userListErrorStatus && ` HTTP ${userListErrorStatus}.`}
                  {userListErrorStatus === 403 && ' Accès refusé : droits administrateur requis.'}
                  {typeof userListErrorDetail === 'string' && ` ${userListErrorDetail}`}
                  {' '}Actualisez pour réessayer.
                </Alert>
              )}
              {!userListQuery.isError && !userListQuery.isFetching && userListQuery.data?.count === 0 && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  {candidates ? 'Aucun utilisateur actif sans association LMS.' : 'Aucune association LMS enregistrée.'}
                </Alert>
              )}
              <UserMappingsTab
                mappings={userListQuery.isError ? [] : userList}
                candidates={candidates}
                canSynchronize={canPublish && !userListQuery.isError && !userListQuery.isFetching}
                onSynchronize={mapping => setUserSynchronization({ mapping, integrationUrl })}
              />
              <PageNavigation
                count={userListQuery.data?.count || 0}
                hasNext={Boolean(userListQuery.data?.next) && !userListQuery.isFetching && !userListQuery.isError}
                hasPrevious={Boolean(userListQuery.data?.previous)
                  && !userListQuery.isFetching && !userListQuery.isError}
                page={userListPage}
                onPageChange={changeUserPage}
              />
            </>
          )}
          {tabValue === 1 && (
            <>
              <Box sx={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2,
              }}
              >
                <Typography variant="h6">Mappings Cours ECUE ↔ LMS</Typography>
                <Button variant="outlined" startIcon={<SyncIcon />} size="small" disabled>
                  Créer cours manquants
                </Button>
              </Box>
              <CourseMappingsTab
                mappings={courseMappings}
                canPublish={canPublish}
                onPublish={mapping => setPublication({ mapping, integrationUrl })}
              />
              <PageNavigation
                count={coursesQuery.data?.count || 0}
                hasNext={Boolean(coursesQuery.data?.next)}
                hasPrevious={Boolean(coursesQuery.data?.previous)}
                page={coursePage}
                onPageChange={setCoursePage}
              />
            </>
          )}
          {tabValue === 2 && (
            <>
              <Box sx={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2,
              }}
              >
                <Typography variant="h6">{failuresOnly ? 'Événements en échec' : 'Événements de synchronisation'}</Typography>
                <Box>
                  {canPublish && (
                    <Button
                      variant="outlined"
                      startIcon={<PlayArrowIcon />}
                      size="small"
                      sx={{ mr: 1 }}
                      disabled={Boolean(outboxAction?.pending)}
                      onClick={processOutbox}
                    >
                      {currentOutboxAction?.pending ? 'Demande en cours…' : 'Demander le traitement'}
                    </Button>
                  )}
                  <Button
                    variant="outlined"
                    color="error"
                    size="small"
                    aria-pressed={failuresOnly}
                    onClick={() => { setFailuresOnly(!failuresOnly); setOutboxPage(1); }}
                  >
                    {failuresOnly ? 'Voir tous les événements' : 'Voir les échecs'}
                  </Button>
                </Box>
              </Box>
              <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                Seuls les événements admissibles de cet établissement sont traités, par lots de 100 au plus.
                Les délais de reprise sont conservés. Les échecs définitifs ne sont ni relancés ni supprimés.
                {failuresOnly && ' Filtre : échecs et échecs définitifs. Les reprises différées restent visibles dans tous les événements.'}
              </Typography>
              {currentOutboxAction?.message && (
                <Alert severity={currentOutboxAction.error ? 'error' : 'info'} sx={{ mb: 2 }}>
                  {currentOutboxAction.message}
                </Alert>
              )}
              <OutboxEventsTab
                events={outboxEvents}
                onDetails={event => setOutboxDetails({ event, integrationUrl })}
              />
              <PageNavigation
                count={outboxQuery.data?.count || 0}
                hasNext={Boolean(outboxQuery.data?.next)}
                hasPrevious={Boolean(outboxQuery.data?.previous)}
                page={outboxPage}
                onPageChange={setOutboxPage}
              />
            </>
          )}
          {tabValue === 3 && (
            <Box>
              <Typography variant="h6" gutterBottom>Configuration de l’intégration</Typography>
              <Alert severity="info" sx={{ mb: 3 }}>
                <AlertTitle>Variables d’environnement requises</AlertTitle>
                Les paramètres de connexion sont configurés via les variables d’environnement du backend.
              </Alert>

              <Grid container spacing={3}>
                <Grid size={{
                  xs: 12,
                  md: 6,
                }}
                >
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                        URLs Open edX
                      </Typography>
                      <List dense>
                        <ListItem>
                          <ListItemText
                            primary="EDX_LMS_URL"
                            secondary={integrationStatus.lms_url || 'Non configuré'}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemText
                            primary="EDX_CMS_URL"
                            secondary={integrationStatus.cms_url || 'Non configuré'}
                          />
                        </ListItem>
                      </List>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{
                  xs: 12,
                  md: 6,
                }}
                >
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                        Synchronisation automatique
                      </Typography>
                      <List dense>
                        <ListItem>
                          <ListItemText primary="Sync utilisateurs à la création" secondary="Activation non vérifiée" />
                          <Switch checked={false} disabled />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Sync inscriptions automatique" secondary="Activation non vérifiée" />
                          <Switch checked={false} disabled />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Import notes depuis LMS" secondary="Activation non vérifiée" />
                          <Switch checked={false} disabled />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Webhooks" secondary="Activation non vérifiée" />
                          <Switch checked={false} disabled />
                        </ListItem>
                      </List>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Box>
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(currentOutboxDetails)} onClose={() => setOutboxDetails(null)} fullWidth maxWidth="sm">
        <DialogTitle>Détails de l’événement {currentOutboxDetails?.id}</DialogTitle>
        <DialogContent>
          <Typography>Type : {currentOutboxDetails?.event_type}</Typography>
          <Typography>Statut : {currentOutboxDetails?.statut_display || currentOutboxDetails?.statut}</Typography>
          <Typography>Tentatives : {currentOutboxDetails?.nb_tentatives}</Typography>
          <Typography>
            Dernière tentative : {currentOutboxDetails?.derniere_tentative
            ? new Date(currentOutboxDetails.derniere_tentative).toLocaleString('fr-FR') : 'Jamais'}
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', mt: 2 }}>
            {currentOutboxDetails?.erreur || 'Aucune erreur enregistrée.'}
          </Typography>
          <Typography variant="body2" color="textSecondary" sx={{ mt: 2 }}>
            Lecture seule. Aucune décision d’accès, version ou preuve d’échec n’est modifiée ici.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOutboxDetails(null)}>Fermer</Button>
        </DialogActions>
      </Dialog>

      <UserSynchronizationDialog
        mapping={selectedUserMapping}
        integrationUrl={integrationUrl}
        canSynchronize={canSynchronizeUser}
        onClose={() => setUserSynchronization(null)}
        onComplete={refreshUserMappings}
      />

      <CoursePublicationDialog
        mapping={publication?.integrationUrl === integrationUrl
          ? courseMappings.find(mapping => mapping.id === publication.mapping.id) || publication.mapping : null}
        canPublish={canPublish}
        onClose={() => setPublication(null)}
      />
    </Box>
  );
};

export default IntegrationLMSPage;
