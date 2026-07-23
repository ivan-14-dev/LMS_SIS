import React, { useState } from 'react';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Sync as SyncIcon,
  Check as CheckIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Person as PersonIcon,
  School as SchoolIcon,
  Assignment as AssignmentIcon,
  CloudSync as CloudSyncIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  Link as LinkIcon,
  LinkOff as LinkOffIcon,
  PlayArrow as PlayArrowIcon,
  Schedule as ScheduleIcon,
  CloudDone as CloudDoneIcon,
  CloudOff as CloudOffIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common';

// Mock data for development
const mockIntegrationStatus = {
  connected: true,
  lms_url: 'http://localhost:18000',
  cms_url: 'http://localhost:18010',
  last_check: '2026-07-23T10:30:00Z',
  version: '18.0.0',
  oauth_status: 'valid',
  webhook_status: 'active',
};

const mockSyncStats = {
  users_mapped: 1245,
  courses_mapped: 48,
  enrollments_active: 3567,
  outbox: {
    pending: 12,
    processing: 3,
    done: 4521,
    failed: 7,
    dead: 2,
  },
  last_sync: '2026-07-23T10:25:00Z',
};

const mockUserMappings = [
  { id: 1, user_sis: 'ETU001 - Jean Dupont', username_edx: 'sis-u-1', user_id_edx: 12345, date_sync: '2026-07-23T09:00:00Z', actif: true },
  { id: 2, user_sis: 'ETU002 - Marie Martin', username_edx: 'sis-u-2', user_id_edx: 12346, date_sync: '2026-07-23T09:00:00Z', actif: true },
  { id: 3, user_sis: 'ENS001 - Prof. Durand', username_edx: 'sis-u-3', user_id_edx: 12347, date_sync: '2026-07-23T08:30:00Z', actif: true },
  { id: 4, user_sis: 'ETU003 - Pierre Leroy', username_edx: 'sis-u-4', user_id_edx: null, date_sync: null, actif: false },
];

const mockCourseMappings = [
  { id: 1, ecue: 'INF101 - Introduction à la Programmation', course_id: 'course-v1:SIS-U+INF101+2025', course_name: 'Introduction à la Programmation 2025', actif: true },
  { id: 2, ecue: 'MAT201 - Algèbre Linéaire', course_id: 'course-v1:SIS-U+MAT201+2025', course_name: 'Algèbre Linéaire 2025', actif: true },
  { id: 3, ecue: 'PHY101 - Physique Générale', course_id: 'course-v1:SIS-U+PHY101+2025', course_name: 'Physique Générale 2025', actif: true },
];

const mockOutboxEvents = [
  { id: 1, event_type: 'user.sync', aggregate_type: 'user', aggregate_id: '45', statut: 'pending', nb_tentatives: 0, created_at: '2026-07-23T10:28:00Z', erreur: '' },
  { id: 2, event_type: 'enrollment.create', aggregate_type: 'etudiant', aggregate_id: '123', statut: 'processing', nb_tentatives: 1, created_at: '2026-07-23T10:25:00Z', erreur: '' },
  { id: 3, event_type: 'grade.sync', aggregate_type: 'note', aggregate_id: '789', statut: 'failed', nb_tentatives: 3, created_at: '2026-07-23T10:20:00Z', erreur: 'Connection timeout' },
];

const StatCard = ({ title, value, icon, color = 'primary', subtitle }) => (
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
        }}>
          {icon}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

const ConnectionStatus = ({ status }) => {
  const isConnected = status?.connected;
  
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
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
            >
              Vérifier
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

const OutboxStatusCard = ({ outbox }) => {
  const total = Object.values(outbox || {}).reduce((a, b) => a + b, 0);
  const pendingPercent = outbox?.pending ? (outbox.pending / total) * 100 : 0;
  
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>File d'attente (Outbox)</Typography>
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
            <TableCell>{mapping.user_sis}</TableCell>
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
                <IconButton size="small" color="primary">
                  <SyncIcon />
                </IconButton>
              </Tooltip>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </TableContainer>
);

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
            <TableCell>{mapping.ecue}</TableCell>
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
                <IconButton size="small" color="primary">
                  <SchoolIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Synchroniser inscriptions">
                <IconButton size="small" color="primary">
                  <SyncIcon />
                </IconButton>
              </Tooltip>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </TableContainer>
);

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
                  <IconButton size="small" color="primary" disabled={event.statut === 'done'}>
                    <PlayArrowIcon />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

const IntegrationLMSPage = () => {
  const [tabValue, setTabValue] = useState(0);
  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  // Using mock data for now
  const integrationStatus = mockIntegrationStatus;
  const syncStats = mockSyncStats;
  const userMappings = mockUserMappings;
  const courseMappings = mockCourseMappings;
  const outboxEvents = mockOutboxEvents;

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
            label: 'Sync complète', 
            icon: <CloudSyncIcon />, 
            variant: 'contained', 
            onClick: () => setSyncDialogOpen(true) 
          },
          { 
            label: 'Paramètres', 
            icon: <SettingsIcon />, 
            variant: 'outlined', 
            onClick: () => {} 
          },
        ]}
      />

      {/* Connection Status */}
      <ConnectionStatus status={integrationStatus} />

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
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">Mappings Utilisateurs SIS ↔ LMS</Typography>
                <Button variant="outlined" startIcon={<SyncIcon />} size="small">
                  Synchroniser tous
                </Button>
              </Box>
              <UserMappingsTab mappings={userMappings} />
            </>
          )}
          {tabValue === 1 && (
            <>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">Mappings Cours ECUE ↔ LMS</Typography>
                <Button variant="outlined" startIcon={<SyncIcon />} size="small">
                  Créer cours manquants
                </Button>
              </Box>
              <CourseMappingsTab mappings={courseMappings} />
            </>
          )}
          {tabValue === 2 && (
            <>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">Événements en attente de synchronisation</Typography>
                <Box>
                  <Button variant="outlined" startIcon={<PlayArrowIcon />} size="small" sx={{ mr: 1 }}>
                    Traiter tous
                  </Button>
                  <Button variant="outlined" color="error" size="small">
                    Purger échecs
                  </Button>
                </Box>
              </Box>
              <OutboxEventsTab events={outboxEvents} />
            </>
          )}
          {tabValue === 3 && (
            <Box>
              <Typography variant="h6" gutterBottom>Configuration de l'intégration</Typography>
              <Alert severity="info" sx={{ mb: 3 }}>
                <AlertTitle>Variables d'environnement requises</AlertTitle>
                Les paramètres de connexion sont configurés via les variables d'environnement du backend.
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
                          <Switch defaultChecked />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Sync inscriptions automatique" />
                          <Switch defaultChecked />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Import notes depuis LMS" />
                          <Switch defaultChecked />
                        </ListItem>
                        <ListItem>
                          <ListItemText primary="Webhooks actifs" />
                          <Switch defaultChecked />
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

      {/* Sync Dialog */}
      <Dialog open={syncDialogOpen} onClose={() => setSyncDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Synchronisation complète</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Cette opération va synchroniser toutes les données entre le SIS et le LMS Open edX.
            Cela peut prendre plusieurs minutes selon le volume de données.
          </Alert>
          <Typography variant="body2" gutterBottom>
            Éléments à synchroniser :
          </Typography>
          <List dense>
            <ListItem>
              <ListItemIcon><PersonIcon /></ListItemIcon>
              <ListItemText primary="Tous les utilisateurs (étudiants, enseignants)" />
            </ListItem>
            <ListItem>
              <ListItemIcon><SchoolIcon /></ListItemIcon>
              <ListItemText primary="Tous les cours (ECUE vers cours LMS)" />
            </ListItem>
            <ListItem>
              <ListItemIcon><AssignmentIcon /></ListItemIcon>
              <ListItemText primary="Toutes les inscriptions aux cours" />
            </ListItem>
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSyncDialogOpen(false)}>Annuler</Button>
          <Button variant="contained" startIcon={<CloudSyncIcon />} onClick={() => setSyncDialogOpen(false)}>
            Lancer la synchronisation
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default IntegrationLMSPage;
