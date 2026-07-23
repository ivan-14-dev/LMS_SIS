import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Avatar,
  Typography,
  Button,
  Grid,
  Chip,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  CircularProgress,
  Divider,
  Stack,
} from '@mui/material';
import {
  Edit as EditIcon,
  Print as PrintIcon,
  Email as EmailIcon,
  Download as DownloadIcon,
  ArrowBack as ArrowBackIcon,
  School as SchoolIcon,
  Phone as PhoneIcon,
  Cake as CakeIcon,
  LocationOn as LocationIcon,
  Public as PublicIcon,
} from '@mui/icons-material';
import { PageHeader, SISDataTable } from '../../components/common';
import { useEtudiant, useInscriptions, useNotes } from '../../services/api';

const EtudiantDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tabValue, setTabValue] = React.useState(0);
  
  const { data: etudiant, isLoading } = useEtudiant(id);
  const { data: inscriptions = [] } = useInscriptions({ etudiant: id });
  const { data: notes = [] } = useNotes({ etudiant: id });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress size={48} />
      </Box>
    );
  }

  if (!etudiant) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant="h6" color="text.secondary">Étudiant non trouvé</Typography>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
          Retour
        </Button>
      </Box>
    );
  }

  // Safe access to name initials
  const getInitials = () => {
    const nom = etudiant.nom || '';
    const prenom = etudiant.prenom || '';
    return (nom[0] || '') + (prenom[0] || '');
  };

  const inscriptionColumns = [
    { Header: 'Année', accessor: 'annee_universitaire' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Niveau', accessor: 'niveau' },
    { Header: 'Semestre', accessor: 'semestre' },
    { 
      Header: 'Statut', 
      accessor: 'statut',
      Cell: ({ value }) => (
        <Chip 
          label={value || 'N/A'} 
          size="small" 
          color={value === 'inscrit' ? 'success' : value === 'en_attente' ? 'warning' : 'default'}
        />
      )
    },
  ];

  const notesColumns = [
    { Header: 'ECUE', accessor: 'ecue_nom' },
    { Header: 'Type', accessor: 'type_evaluation' },
    { 
      Header: 'Note', 
      accessor: 'note',
      Cell: ({ value }) => (
        <Chip 
          label={value !== undefined && value !== null ? value + '/20' : '-'} 
          size="small"
          color={value >= 10 ? 'success' : value !== undefined ? 'error' : 'default'}
        />
      )
    },
    { Header: 'Session', accessor: 'session' },
  ];

  const InfoRow = ({ icon, label, value }) => (
    <Box sx={{ display: 'flex', alignItems: 'center', py: 1 }}>
      {icon}
      <Box sx={{ ml: 2 }}>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography variant="body2">{value || 'Non renseigné'}</Typography>
      </Box>
    </Box>
  );

  return (
    <Box>
      <PageHeader
        title={`${etudiant.nom || ''} ${etudiant.prenom || ''}`}
        subtitle={`Matricule: ${etudiant.matricule || 'N/A'}`}
        showBack
        breadcrumbs={[
          { label: 'Étudiants', path: '/superieur/etudiants' },
          { label: etudiant.nom || 'Détail' },
        ]}
        actions={[
          { label: 'Imprimer', icon: <PrintIcon />, variant: 'outlined', onClick: () => window.print() },
          { label: 'Email', icon: <EmailIcon />, variant: 'outlined', onClick: () => window.location.href = 'mailto:' + (etudiant.email || '') },
          { label: 'Modifier', icon: <EditIcon />, variant: 'contained', onClick: () => navigate('edit') },
        ]}
      />

      <Grid container spacing={3}>
        {/* Profile Card */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent sx={{ textAlign: 'center', pt: 4 }}>
              <Avatar 
                sx={{ 
                  width: 100, 
                  height: 100, 
                  fontSize: '2.5rem', 
                  bgcolor: 'primary.main',
                  mx: 'auto',
                  mb: 2 
                }}
              >
                {getInitials()}
              </Avatar>
              <Typography variant="h5" fontWeight={600}>
                {etudiant.nom || ''} {etudiant.prenom || ''}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {etudiant.formation_nom || 'Formation non assignée'}
              </Typography>
              <Chip 
                label={etudiant.statut === 'actif' ? 'Actif' : 'Inactif'} 
                color={etudiant.statut === 'actif' ? 'success' : 'default'}
                size="small"
                sx={{ mt: 1 }}
              />
            </CardContent>
            <Divider />
            <CardContent>
              <InfoRow icon={<EmailIcon color="action" />} label="Email" value={etudiant.email} />
              <InfoRow icon={<PhoneIcon color="action" />} label="Téléphone" value={etudiant.telephone} />
              <InfoRow icon={<CakeIcon color="action" />} label="Date de naissance" value={etudiant.date_naissance} />
              <InfoRow icon={<LocationIcon color="action" />} label="Lieu de naissance" value={etudiant.lieu_naissance} />
              <InfoRow icon={<PublicIcon color="action" />} label="Nationalité" value={etudiant.nationalite} />
            </CardContent>
          </Card>

          {/* Quick Stats */}
          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                Statistiques
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', p: 1, bgcolor: 'primary.lighter', borderRadius: 1 }}>
                    <Typography variant="h4" color="primary.main" fontWeight={700}>
                      {Array.isArray(inscriptions) ? inscriptions.length : 0}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">Inscriptions</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box sx={{ textAlign: 'center', p: 1, bgcolor: 'success.lighter', borderRadius: 1 }}>
                    <Typography variant="h4" color="success.main" fontWeight={700}>
                      {Array.isArray(notes) ? notes.length : 0}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">Notes</Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Details Tabs */}
        <Grid item xs={12} md={8}>
          <Card>
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
                <Tab label="Inscriptions" />
                <Tab label="Notes" />
                <Tab label="Documents" />
              </Tabs>
            </Box>
            
            {tabValue === 0 && (
              <Box sx={{ p: 2 }}>
                <SISDataTable
                  title="Historique des inscriptions"
                  data={inscriptions}
                  columns={inscriptionColumns}
                  searchable={false}
                  exportable={false}
                  pageSize={5}
                  emptyMessage="Aucune inscription trouvée"
                />
              </Box>
            )}
            
            {tabValue === 1 && (
              <Box sx={{ p: 2 }}>
                <SISDataTable
                  title="Relevé de notes"
                  data={notes}
                  columns={notesColumns}
                  searchable={false}
                  pageSize={10}
                  emptyMessage="Aucune note enregistrée"
                />
              </Box>
            )}
            
            {tabValue === 2 && (
              <Box sx={{ p: 2 }}>
                <List>
                  {[
                    { name: 'Certificat de scolarité', type: 'PDF' },
                    { name: 'Relevé de notes', type: 'PDF' },
                    { name: 'Attestation d\'inscription', type: 'PDF' },
                    { name: 'Carte d\'étudiant', type: 'PDF' },
                  ].map((doc, idx) => (
                    <ListItem key={idx} divider={idx < 3}>
                      <ListItemText primary={doc.name} secondary={doc.type} />
                      <ListItemSecondaryAction>
                        <Button 
                          size="small" 
                          variant="outlined" 
                          startIcon={<DownloadIcon />}
                          onClick={() => alert('Téléchargement de ' + doc.name)}
                        >
                          Télécharger
                        </Button>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default EtudiantDetailPage;
