import React, { useState } from 'react';
import PropTypes from 'prop-types';
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
  Link as LinkIcon,
  LinkOff as LinkOffIcon,
  PlayArrow as PlayArrowIcon,
  Schedule as ScheduleIcon,
  CloudDone as CloudDoneIcon,
  CloudOff as CloudOffIcon,
} from '@mui/icons-material';
import { PageHeader } from '../../components/common';
import {
  useIntegrationCourseMappings,
  useIntegrationHealth,
  useIntegrationOutboxEvents,
  useIntegrationStats,
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
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2,
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
              label={isConnected ? 'Connecté' : 'Déconnecté'}
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

        <Grid container spacing={3}>
          <Grid item xs={12} md={3}>
            <Typography variant="body2" color="textSecondary">Version LMS</Typography>
            <Typography variant="body1" fontWeight={500}>{status?.version || '-'}</Typography>
          </Grid>
          <Grid item xs={12} md={3}>
            <Typography variant="body2" color="textSecondary">OAuth</Typography>
            <Chip
              size="small"
              label={status?.oauth_status || 'N/A'}
              color={status?.oauth_status === 'valid' ? 'success' : 'warning'}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <Typography variant="body2" color="textSecondary">Webhooks</Typography>
            <Chip
              size="small"
              label={status?.webhook_status || 'N/A'}
              color={status?.webhook_status === 'active' ? 'success' : 'warning'}
            />
          </Grid>
          <Grid item xs={12} md={3}>
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
          <Grid item xs={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Chip label={outbox?.pending || 0} color="warning" size="small" />
              <Typography variant="caption" display="block">En attente</Typography>
            </Box>
          </Grid>
          <Grid item xs={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Chip label={outbox?.processing || 0} color="info" size="small" />
              <Typography variant="caption" display="block">En cours</Typography>
            </Box>
          </Grid>
          <Grid item xs={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Chip label={outbox?.failed || 0} color="error" size="small" />
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
  }),
};

OutboxStatusCard.defaultProps = {
  outbox: {},
};

const UserMappingsTab = ({ mappings }) => (
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
          <TableRow key={mapping.id}>
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
              <Chip
                icon={mapping.actif ? <LinkIcon /> : <LinkOffIcon />}
                label={mapping.actif ? 'Actif' : 'Inactif'}
                color={mapping.actif ? 'success' : 'default'}
                size="small"
              />
            </TableCell>
            <TableCell align="right">
              <Tooltip title="Synchroniser">
                <span>
                  <IconButton size="small" color="primary" disabled>
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

UserMappingsTab.propTypes = {
  mappings: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    user_sis: PropTypes.number,
    user_sis_name: PropTypes.string,
    user_sis_username: PropTypes.string,
    username_edx: PropTypes.string.isRequired,
    user_id_edx: PropTypes.number,
    date_sync: PropTypes.string,
    actif: PropTypes.bool.isRequired,
  })).isRequired,
};

const CourseMappingsTab = ({ mappings }) => (
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
              <Chip
                label={mapping.actif ? 'Actif' : 'Inactif'}
                color={mapping.actif ? 'success' : 'default'}
                size="small"
              />
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
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </TableContainer>
);

CourseMappingsTab.propTypes = {
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

const OutboxEventsTab = ({ events }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'warning';
      case 'processing': return 'info';
      case 'done': return 'success';
      case 'failed': return 'error';
      case 'dead': return 'default';
      default: return 'default';
    }
  };

  return (
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
                <Chip
                  label={event.statut}
                  color={getStatusColor(event.statut)}
                  size="small"
                />
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
                <Tooltip title="Relancer">
                  <span>
                    <IconButton size="small" color="primary" disabled>
                      <PlayArrowIcon />
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

OutboxEventsTab.propTypes = {
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
}) => (
  <Box sx={{
    alignItems: 'center', display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 2,
  }}
  >
    <Typography variant="body2" color="textSecondary">
      {count}
      {' '}
      résultat(s) — page
      {' '}
      {page}
    </Typography>
    <Button
      size="small"
      disabled={!hasPrevious}
      onClick={() => onPageChange(page - 1)}
    >
      Précédent
    </Button>
    <Button
      size="small"
      disabled={!hasNext}
      onClick={() => onPageChange(page + 1)}
    >
      Suivant
    </Button>
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
  const [tabValue, setTabValue] = useState(0);
  const [userPage, setUserPage] = useState(1);
  const [coursePage, setCoursePage] = useState(1);
  const [outboxPage, setOutboxPage] = useState(1);
  const healthQuery = useIntegrationHealth();
  const statsQuery = useIntegrationStats();
  const usersQuery = useIntegrationUserMappings(userPage);
  const coursesQuery = useIntegrationCourseMappings(coursePage);
  const outboxQuery = useIntegrationOutboxEvents(outboxPage);

  const integrationStatus = healthQuery.data || {};
  const syncStats = statsQuery.data || {};
  const userMappings = usersQuery.data?.results || [];
  const courseMappings = coursesQuery.data?.results || [];
  const outboxEvents = outboxQuery.data?.results || [];
  const queries = [healthQuery, statsQuery, usersQuery, coursesQuery, outboxQuery];
  const isLoading = queries.some(query => query.isLoading);
  const isRefreshing = queries.some(query => query.isFetching);
  const hasError = queries.some(query => query.isError);

  const refresh = () => Promise.all(queries.map(query => query.refetch()));

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  return (
    <Box sx={{ p: 3 }}>
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
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Utilisateurs mappés"
            value={syncStats.users_mapped?.toLocaleString()}
            icon={<PersonIcon />}
            color="primary"
            subtitle="Synchronisés avec LMS"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Cours mappés"
            value={syncStats.courses_mapped}
            icon={<SchoolIcon />}
            color="success"
            subtitle="ECUE → Cours LMS"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Inscriptions actives"
            value={syncStats.enrollments_active?.toLocaleString()}
            icon={<AssignmentIcon />}
            color="info"
            subtitle="Étudiants inscrits aux cours"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
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
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2,
              }}
              >
                <Typography variant="h6">Mappings Utilisateurs SIS ↔ LMS</Typography>
                <Button variant="outlined" startIcon={<SyncIcon />} size="small" disabled>
                  Synchroniser tous
                </Button>
              </Box>
              <UserMappingsTab mappings={userMappings} />
              <PageNavigation
                count={usersQuery.data?.count || 0}
                hasNext={Boolean(usersQuery.data?.next)}
                hasPrevious={Boolean(usersQuery.data?.previous)}
                page={userPage}
                onPageChange={setUserPage}
              />
            </>
          )}
          {tabValue === 1 && (
            <>
              <Box sx={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2,
              }}
              >
                <Typography variant="h6">Mappings Cours ECUE ↔ LMS</Typography>
                <Button variant="outlined" startIcon={<SyncIcon />} size="small" disabled>
                  Créer cours manquants
                </Button>
              </Box>
              <CourseMappingsTab mappings={courseMappings} />
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
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2,
              }}
              >
                <Typography variant="h6">Événements en attente de synchronisation</Typography>
                <Box>
                  <Button variant="outlined" startIcon={<PlayArrowIcon />} size="small" sx={{ mr: 1 }} disabled>
                    Traiter tous
                  </Button>
                  <Button variant="outlined" color="error" size="small" disabled>
                    Purger échecs
                  </Button>
                </Box>
              </Box>
              <OutboxEventsTab events={outboxEvents} />
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
                <Grid item xs={12} md={6}>
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
                <Grid item xs={12} md={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                        Synchronisation automatique
                      </Typography>
                      <List dense>
                        <ListItem>
                          <ListItemText primary="Sync utilisateurs à la création" />
                          <Switch checked disabled />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Sync inscriptions automatique" />
                          <Switch checked disabled />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Import notes depuis LMS" />
                          <Switch checked disabled />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Webhooks actifs" />
                          <Switch checked disabled />
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

    </Box>
  );
};

export default IntegrationLMSPage;
