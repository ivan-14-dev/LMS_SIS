import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Avatar,
  LinearProgress,
  IconButton,
  Button,
  Paper,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  Divider,
  useTheme,
} from '@mui/material';
import {
  People as PeopleIcon,
  School as SchoolIcon,
  Assignment as AssignmentIcon,
  TrendingUp as TrendingUpIcon,
  EventNote as EventNoteIcon,
  AttachMoney as MoneyIcon,
  ArrowForward as ArrowForwardIcon,
  Add as AddIcon,
  PersonAdd as PersonAddIcon,
  NoteAdd as NoteAddIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { fetchApi, getSuperieurApiUrl } from '../services/api';

// Stat Card Component
const StatCard = ({ title, value, icon, color, trend, trendLabel, onClick }) => {
  const theme = useTheme();
  
  return (
    <Card 
      sx={{ 
        cursor: onClick ? 'pointer' : 'default',
        height: '100%',
        position: 'relative',
        overflow: 'visible',
      }}
      onClick={onClick}
    >
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="overline" color="text.secondary" gutterBottom>
              {title}
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary', my: 1 }}>
              {value}
            </Typography>
            {trend && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TrendingUpIcon sx={{ fontSize: 16, color: trend > 0 ? 'success.main' : 'error.main' }} />
                <Typography variant="caption" color={trend > 0 ? 'success.main' : 'error.main'} fontWeight={600}>
                  {trend > 0 ? '+' : ''}{trend}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {trendLabel}
                </Typography>
              </Box>
            )}
          </Box>
          <Avatar 
            sx={{ 
              width: 56, 
              height: 56, 
              bgcolor: `${color}.main`,
              boxShadow: `0 8px 16px ${theme.palette[color]?.main}40`,
            }}
          >
            {icon}
          </Avatar>
        </Box>
      </CardContent>
    </Card>
  );
};

// Quick Action Card
const QuickActionCard = ({ title, description, icon, color, onClick }) => (
  <Card 
    sx={{ 
      cursor: 'pointer',
      transition: 'all 0.2s',
      '&:hover': {
        transform: 'translateY(-4px)',
        boxShadow: 4,
      },
    }}
    onClick={onClick}
  >
    <CardContent sx={{ p: 2.5, display: 'flex', alignItems: 'center', gap: 2 }}>
      <Avatar sx={{ bgcolor: `${color}.light`, color: `${color}.main` }}>
        {icon}
      </Avatar>
      <Box>
        <Typography variant="subtitle2" fontWeight={600}>{title}</Typography>
        <Typography variant="caption" color="text.secondary">{description}</Typography>
      </Box>
    </CardContent>
  </Card>
);

const ModernDashboard = () => {
  const navigate = useNavigate();
  const theme = useTheme();

  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/dashboard/stats/`),
  });

  const { data: activities } = useQuery({
    queryKey: ['recent-activities'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/dashboard/activites/`),
  });

  const recentActivities = activities || [];

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Tableau de bord
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Bienvenue ! Voici un aperçu de votre système d'information universitaire.
        </Typography>
      </Box>

      {/* Stats Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Étudiants"
            value={isLoading ? '...' : (stats?.etudiants?.toLocaleString() || '12,450')}
            icon={<PeopleIcon />}
            color="primary"
            trend={5.2}
            trendLabel="ce mois"
            onClick={() => navigate('/superieur/etudiants')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Enseignants"
            value={isLoading ? '...' : (stats?.enseignants?.toLocaleString() || '856')}
            icon={<SchoolIcon />}
            color="secondary"
            trend={2.1}
            trendLabel="ce mois"
            onClick={() => navigate('/superieur/enseignants')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Cours Actifs"
            value={isLoading ? '...' : (stats?.cours_actifs?.toLocaleString() || '342')}
            icon={<AssignmentIcon />}
            color="success"
            trend={8.5}
            trendLabel="ce semestre"
            onClick={() => navigate('/superieur/formations')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Inscriptions"
            value={isLoading ? '...' : (stats?.inscriptions_semestre?.toLocaleString() || '14,520')}
            icon={<EventNoteIcon />}
            color="warning"
            trend={12.3}
            trendLabel="vs. dernier semestre"
            onClick={() => navigate('/superieur/inscriptions')}
          />
        </Grid>
      </Grid>

      {/* Quick Stats Row */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h6" fontWeight={600}>Progression des Inscriptions</Typography>
                <Chip label="Semestre en cours" size="small" color="primary" />
              </Box>
              
              <Grid container spacing={3}>
                <Grid item xs={12} md={4}>
                  <Box sx={{ textAlign: 'center', p: 2 }}>
                    <Typography variant="h3" fontWeight={700} color="primary.main">85%</Typography>
                    <Typography variant="body2" color="text.secondary">Taux de réussite</Typography>
                    <LinearProgress 
                      variant="determinate" 
                      value={85} 
                      sx={{ mt: 1, height: 8, borderRadius: 4 }}
                    />
                  </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Box sx={{ textAlign: 'center', p: 2 }}>
                    <Typography variant="h3" fontWeight={700} color="secondary.main">92%</Typography>
                    <Typography variant="body2" color="text.secondary">Taux de présence</Typography>
                    <LinearProgress 
                      variant="determinate" 
                      value={92} 
                      color="secondary"
                      sx={{ mt: 1, height: 8, borderRadius: 4 }}
                    />
                  </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Box sx={{ textAlign: 'center', p: 2 }}>
                    <Typography variant="h3" fontWeight={700} color="success.main">78%</Typography>
                    <Typography variant="body2" color="text.secondary">Objectif atteint</Typography>
                    <LinearProgress 
                      variant="determinate" 
                      value={78} 
                      color="success"
                      sx={{ mt: 1, height: 8, borderRadius: 4 }}
                    />
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Actions Rapides
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                <Button 
                  variant="contained" 
                  startIcon={<PersonAddIcon />}
                  onClick={() => navigate('/superieur/etudiants')}
                  fullWidth
                  sx={{ justifyContent: 'flex-start', py: 1.5 }}
                >
                  Nouvel étudiant
                </Button>
                <Button 
                  variant="outlined" 
                  startIcon={<NoteAddIcon />}
                  onClick={() => navigate('/superieur/notes')}
                  fullWidth
                  sx={{ justifyContent: 'flex-start', py: 1.5 }}
                >
                  Saisir des notes
                </Button>
                <Button 
                  variant="outlined" 
                  startIcon={<EventNoteIcon />}
                  onClick={() => navigate('/superieur/examens')}
                  fullWidth
                  sx={{ justifyContent: 'flex-start', py: 1.5 }}
                >
                  Planifier un examen
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Activity & Quick Actions */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent sx={{ p: 0 }}>
              <Box sx={{ p: 3, pb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="h6" fontWeight={600}>Activités Récentes</Typography>
                <Button size="small" endIcon={<ArrowForwardIcon />}>Voir tout</Button>
              </Box>
              <List sx={{ py: 0 }}>
                {(recentActivities.length > 0 ? recentActivities : [
                  { id: 1, type: 'inscription', message: 'Nouvel étudiant inscrit: Ahmed BENNANI', date: '10:30' },
                  { id: 2, type: 'note', message: 'Notes saisies pour Mathématiques L2', date: '09:15' },
                  { id: 3, type: 'paiement', message: 'Paiement reçu: 15000 MAD', date: '08:45' },
                ]).map((activity, index) => (
                  <React.Fragment key={activity.id}>
                    <ListItem sx={{ px: 3, py: 2 }}>
                      <ListItemAvatar>
                        <Avatar sx={{ 
                          bgcolor: activity.type === 'inscription' ? 'primary.light' 
                            : activity.type === 'note' ? 'success.light' 
                            : 'warning.light',
                          color: activity.type === 'inscription' ? 'primary.main' 
                            : activity.type === 'note' ? 'success.main' 
                            : 'warning.main',
                        }}>
                          {activity.type === 'inscription' && <PersonAddIcon />}
                          {activity.type === 'note' && <AssignmentIcon />}
                          {activity.type === 'paiement' && <MoneyIcon />}
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={activity.message}
                        secondary={activity.date}
                        primaryTypographyProps={{ fontWeight: 500, fontSize: '0.875rem' }}
                      />
                    </ListItem>
                    {index < 2 && <Divider component="li" />}
                  </React.Fragment>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>Accès Portails</Typography>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                <Grid item xs={6}>
                  <QuickActionCard
                    title="Portail Apprenant/Famille"
                    description="Accès étudiant"
                    icon={<PeopleIcon />}
                    color="primary"
                    onClick={() => navigate('/superieur/portail-apprenant')}
                  />
                </Grid>
                <Grid item xs={6}>
                  <QuickActionCard
                    title="Portail Staff/Admin"
                    description="Accès personnel et administration"
                    icon={<SchoolIcon />}
                    color="secondary"
                    onClick={() => navigate('/superieur/portail-staff')}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Year indicator */}
      <Paper 
        sx={{ 
          mt: 4, 
          p: 2, 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center',
          gap: 2,
          bgcolor: 'primary.main',
          color: 'white',
          borderRadius: 3,
        }}
      >
        <Typography variant="h6" fontWeight={600}>
          Année Universitaire 2025-2026
        </Typography>
        <Chip label="Semestre 1 en cours" sx={{ bgcolor: 'white', color: 'primary.main', fontWeight: 600 }} />
      </Paper>
    </Box>
  );
};

export default ModernDashboard;
