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
  Button,
  Paper,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Divider,
  Chip,
  useTheme,
} from '@mui/material';
import {
  People as PeopleIcon,
  Class as ClassIcon,
  Star as StarIcon,
  EventNote as EventNoteIcon,
  TrendingUp as TrendingUpIcon,
  PersonAdd as PersonAddIcon,
  Edit as EditIcon,
  Assignment as AssignmentIcon,
  Print as PrintIcon,
  Fastfood as FastfoodIcon,
  DirectionsBus as BusIcon,
  LocalHospital as HealthIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { fetchApi, getSecondaireApiUrl } from '../services/api';

const StatCard = ({ title, value, icon, color, trend, onClick }) => {
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
                <TrendingUpIcon sx={{ fontSize: 16, color: 'success.main' }} />
                <Typography variant="caption" color="success.main" fontWeight={600}>
                  +{trend}%
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

const Dashboard = () => {
  const navigate = useNavigate();
  const theme = useTheme();

  const { data: stats, isLoading } = useQuery({
    queryKey: ['secondaire-stats'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/dashboard/stats/`),
  });

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Tableau de bord
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Vue d'ensemble du système d'information scolaire
        </Typography>
      </Box>

      {/* Stats Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Élèves inscrits"
            value={isLoading ? '...' : (stats?.eleves?.toLocaleString() || '1,250')}
            icon={<PeopleIcon />}
            color="primary"
            trend={3.2}
            onClick={() => navigate('/secondaire/eleves')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Classes"
            value={isLoading ? '...' : (stats?.classes?.toLocaleString() || '42')}
            icon={<ClassIcon />}
            color="secondary"
            onClick={() => navigate('/secondaire/classes')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Moyenne générale"
            value={isLoading ? '...' : (stats?.moyenne_generale || '13.5/20')}
            icon={<StarIcon />}
            color="warning"
            onClick={() => navigate('/secondaire/evaluations')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Taux présence"
            value={isLoading ? '...' : (stats?.taux_presence || '94%')}
            icon={<EventNoteIcon />}
            color="success"
            onClick={() => navigate('/secondaire/presences')}
          />
        </Grid>
      </Grid>

      {/* Actions & Activities Row */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Actions rapides
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                <Button 
                  variant="contained" 
                  startIcon={<PersonAddIcon />}
                  onClick={() => navigate('/secondaire/eleves')}
                  fullWidth
                  sx={{ justifyContent: 'flex-start', py: 1.5 }}
                >
                  Nouvel élève
                </Button>
                <Button 
                  variant="outlined" 
                  startIcon={<EditIcon />}
                  onClick={() => navigate('/secondaire/presences')}
                  fullWidth
                  sx={{ justifyContent: 'flex-start', py: 1.5 }}
                >
                  Saisir les présences
                </Button>
                <Button 
                  variant="outlined" 
                  startIcon={<AssignmentIcon />}
                  onClick={() => navigate('/secondaire/evaluations')}
                  fullWidth
                  sx={{ justifyContent: 'flex-start', py: 1.5 }}
                >
                  Saisir des notes
                </Button>
                <Button 
                  variant="outlined" 
                  startIcon={<PrintIcon />}
                  onClick={() => navigate('/secondaire/bulletins')}
                  fullWidth
                  sx={{ justifyContent: 'flex-start', py: 1.5 }}
                >
                  Générer bulletins
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h6" fontWeight={600}>Statistiques par niveau</Typography>
                <Chip label="Année 2025-2026" size="small" color="primary" />
              </Box>
              
              <Grid container spacing={3}>
                {[
                  { level: '6ème', students: 320, average: 12.8 },
                  { level: '5ème', students: 305, average: 13.2 },
                  { level: '4ème', students: 298, average: 12.5 },
                  { level: '3ème', students: 327, average: 14.1 },
                ].map((item) => (
                  <Grid item xs={6} md={3} key={item.level}>
                    <Box sx={{ textAlign: 'center', p: 2, border: 1, borderColor: 'divider', borderRadius: 2 }}>
                      <Typography variant="h6" fontWeight={700} color="primary.main">{item.level}</Typography>
                      <Typography variant="body2" color="text.secondary">{item.students} élèves</Typography>
                      <Typography variant="caption" color="success.main">Moy: {item.average}/20</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Services Row */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Avatar sx={{ bgcolor: 'warning.light', color: 'warning.main' }}>
                  <FastfoodIcon />
                </Avatar>
                <Typography variant="h6" fontWeight={600}>Cantine</Typography>
              </Box>
              <Typography variant="h4" fontWeight={700}>892</Typography>
              <Typography variant="body2" color="text.secondary">Inscrits cette semaine</Typography>
              <LinearProgress variant="determinate" value={71} sx={{ mt: 2, height: 8, borderRadius: 4 }} />
              <Button size="small" sx={{ mt: 2 }} onClick={() => navigate('/secondaire/cantine')}>
                Voir détails →
              </Button>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Avatar sx={{ bgcolor: 'info.light', color: 'info.main' }}>
                  <BusIcon />
                </Avatar>
                <Typography variant="h6" fontWeight={600}>Transport</Typography>
              </Box>
              <Typography variant="h4" fontWeight={700}>12</Typography>
              <Typography variant="body2" color="text.secondary">Lignes actives</Typography>
              <LinearProgress variant="determinate" value={100} color="info" sx={{ mt: 2, height: 8, borderRadius: 4 }} />
              <Button size="small" sx={{ mt: 2 }} onClick={() => navigate('/secondaire/transport')}>
                Voir détails →
              </Button>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Avatar sx={{ bgcolor: 'error.light', color: 'error.main' }}>
                  <HealthIcon />
                </Avatar>
                <Typography variant="h6" fontWeight={600}>Infirmerie</Typography>
              </Box>
              <Typography variant="h4" fontWeight={700}>15</Typography>
              <Typography variant="body2" color="text.secondary">Visites aujourd'hui</Typography>
              <LinearProgress variant="determinate" value={30} color="error" sx={{ mt: 2, height: 8, borderRadius: 4 }} />
              <Button size="small" sx={{ mt: 2 }} onClick={() => navigate('/secondaire/infirmerie')}>
                Voir détails →
              </Button>
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
          bgcolor: 'secondary.main',
          color: 'white',
          borderRadius: 3,
        }}
      >
        <Typography variant="h6" fontWeight={600}>
          Année Scolaire 2025-2026
        </Typography>
        <Chip label="2ème Trimestre en cours" sx={{ bgcolor: 'white', color: 'secondary.main', fontWeight: 600 }} />
      </Paper>
    </Box>
  );
};

export default Dashboard;
