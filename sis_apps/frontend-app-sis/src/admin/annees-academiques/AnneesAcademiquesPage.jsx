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
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  LinearProgress,
  Stepper,
  Step,
  StepLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Switch,
  FormControlLabel,
  Tooltip,
  Avatar,
  Stack,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as ActivateIcon,
  Stop as CloseIcon,
  CalendarMonth as CalendarIcon,
  School as SchoolIcon,
  CheckCircle as CheckIcon,
  Warning as WarningIcon,
  TrendingUp as PromoteIcon,
  Schedule as ScheduleIcon,
  Group as GroupIcon,
  ArrowUpward as UpIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { PageHeader, StatCard } from '../../components/common';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi, getSuperieurApiUrl, getSecondaireApiUrl } from '../../services/api';

// Mock data for demo
const mockAnneesUniv = [
  { id: 1, libelle: '2025-2026', date_debut: '2025-09-01', date_fin: '2026-06-30', en_cours: true, cloturee: false, semestres: 2 },
  { id: 2, libelle: '2024-2025', date_debut: '2024-09-01', date_fin: '2025-06-30', en_cours: false, cloturee: true, semestres: 2 },
  { id: 3, libelle: '2023-2024', date_debut: '2023-09-01', date_fin: '2024-06-30', en_cours: false, cloturee: true, semestres: 2 },
];

const mockSemestres = [
  { id: 1, numero: 1, type: 'impair', date_debut: '2025-09-01', date_fin: '2026-01-31', cloture: false, annee: '2025-2026' },
  { id: 2, numero: 2, type: 'pair', date_debut: '2026-02-01', date_fin: '2026-06-30', cloture: false, annee: '2025-2026' },
];

const mockAnneesScol = [
  { id: 1, libelle: '2025-2026', date_debut: '2025-09-01', date_fin: '2026-06-30', en_cours: true, cloturee: false, periodes: 3 },
  { id: 2, libelle: '2024-2025', date_debut: '2024-09-01', date_fin: '2025-06-30', en_cours: false, cloturee: true, periodes: 3 },
];

const mockPeriodes = [
  { id: 1, type: 'trimestre', numero: 1, libelle: '1er Trimestre', date_debut: '2025-09-01', date_fin: '2025-12-15', cloturee: false },
  { id: 2, type: 'trimestre', numero: 2, libelle: '2ème Trimestre', date_debut: '2026-01-05', date_fin: '2026-03-20', cloturee: false },
  { id: 3, type: 'trimestre', numero: 3, libelle: '3ème Trimestre', date_debut: '2026-04-01', date_fin: '2026-06-30', cloturee: false },
];

const mockElevesPromo = [
  { id: 1, nom: 'BENNANI Ahmed', classe_actuelle: '2nde A', classe_suivante: '1ère S', moyenne: 14.5, decision: 'passage' },
  { id: 2, nom: 'FILALI Leila', classe_actuelle: '2nde A', classe_suivante: '1ère S', moyenne: 16.2, decision: 'passage' },
  { id: 3, nom: 'ALAMI Omar', classe_actuelle: '2nde A', classe_suivante: null, moyenne: 8.5, decision: 'redoublement' },
  { id: 4, nom: 'TAHIRI Sara', classe_actuelle: '2nde A', classe_suivante: '1ère L', moyenne: 12.0, decision: 'passage' },
];

const AnneesAcademiquesPage = () => {
  const [tabValue, setTabValue] = useState(0);
  const [openDialog, setOpenDialog] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [promotionStep, setPromotionStep] = useState(0);
  const queryClient = useQueryClient();

  // Tab panels: 0=Supérieur, 1=Secondaire, 2=Promotion
  
  const handleOpenDialog = (type, item = null) => {
    setSelectedItem(item);
    setOpenDialog(type);
  };

  const handleCloseDialog = () => {
    setOpenDialog(null);
    setSelectedItem(null);
  };

  // ===================== SUPÉRIEUR TAB =====================
  const renderSuperieurTab = () => (
    <Box>
      {/* Stats */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'primary.lighter' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4" fontWeight={700} color="primary.main">2025-2026</Typography>
                  <Typography variant="body2" color="text.secondary">Année en cours</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'primary.main' }}><CalendarIcon /></Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'success.lighter' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4" fontWeight={700} color="success.main">S1</Typography>
                  <Typography variant="body2" color="text.secondary">Semestre actif</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'success.main' }}><ScheduleIcon /></Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'info.lighter' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4" fontWeight={700} color="info.main">14,520</Typography>
                  <Typography variant="body2" color="text.secondary">Étudiants inscrits</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'info.main' }}><GroupIcon /></Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'warning.lighter' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4" fontWeight={700} color="warning.main">45</Typography>
                  <Typography variant="body2" color="text.secondary">Jours restants</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'warning.main' }}><WarningIcon /></Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Années universitaires */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6" fontWeight={600}>Années Universitaires</Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpenDialog('annee-univ')}>
              Nouvelle année
            </Button>
          </Box>
        </CardContent>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Année</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Dates</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Semestres</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Statut</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mockAnneesUniv.map((annee) => (
                <TableRow key={annee.id} hover>
                  <TableCell>
                    <Typography fontWeight={600}>{annee.libelle}</Typography>
                  </TableCell>
                  <TableCell>
                    {annee.date_debut} → {annee.date_fin}
                  </TableCell>
                  <TableCell>
                    <Chip label={`${annee.semestres} semestres`} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    {annee.en_cours ? (
                      <Chip label="En cours" color="success" size="small" icon={<CheckIcon />} />
                    ) : annee.cloturee ? (
                      <Chip label="Clôturée" color="default" size="small" />
                    ) : (
                      <Chip label="Inactive" color="warning" size="small" />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                      {!annee.en_cours && !annee.cloturee && (
                        <Tooltip title="Activer">
                          <IconButton color="success" size="small" onClick={() => handleOpenDialog('activer-annee', annee)}>
                            <ActivateIcon />
                          </IconButton>
                        </Tooltip>
                      )}
                      {annee.en_cours && (
                        <Tooltip title="Clôturer">
                          <IconButton color="warning" size="small" onClick={() => handleOpenDialog('cloturer-annee', annee)}>
                            <CloseIcon />
                          </IconButton>
                        </Tooltip>
                      )}
                      <Tooltip title="Modifier">
                        <IconButton size="small" onClick={() => handleOpenDialog('edit-annee-univ', annee)}>
                          <EditIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Gérer semestres">
                        <IconButton size="small" color="primary" onClick={() => handleOpenDialog('semestres', annee)}>
                          <ScheduleIcon />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Semestres de l'année en cours */}
      <Card>
        <CardContent sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6" fontWeight={600}>Semestres 2025-2026</Typography>
            <Button variant="outlined" startIcon={<AddIcon />} onClick={() => handleOpenDialog('semestre')}>
              Ajouter semestre
            </Button>
          </Box>
        </CardContent>
        <List>
          {mockSemestres.map((sem, idx) => (
            <React.Fragment key={sem.id}>
              <ListItem>
                <Avatar sx={{ bgcolor: sem.cloture ? 'grey.400' : 'primary.main', mr: 2 }}>
                  S{sem.numero}
                </Avatar>
                <ListItemText
                  primary={`Semestre ${sem.numero} (${sem.type})`}
                  secondary={`${sem.date_debut} → ${sem.date_fin}`}
                />
                <ListItemSecondaryAction>
                  <Stack direction="row" spacing={1} alignItems="center">
                    {sem.cloture ? (
                      <Chip label="Clôturé" size="small" color="default" />
                    ) : (
                      <>
                        <Chip label="En cours" size="small" color="success" />
                        <Button size="small" variant="outlined" color="warning" onClick={() => handleOpenDialog('cloturer-semestre', sem)}>
                          Clôturer
                        </Button>
                      </>
                    )}
                    <IconButton size="small"><EditIcon /></IconButton>
                  </Stack>
                </ListItemSecondaryAction>
              </ListItem>
              {idx < mockSemestres.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </List>
      </Card>
    </Box>
  );

  // ===================== SECONDAIRE TAB =====================
  const renderSecondaireTab = () => (
    <Box>
      {/* Stats */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'secondary.lighter' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4" fontWeight={700} color="secondary.main">2025-2026</Typography>
                  <Typography variant="body2" color="text.secondary">Année scolaire</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'secondary.main' }}><SchoolIcon /></Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'success.lighter' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4" fontWeight={700} color="success.main">T2</Typography>
                  <Typography variant="body2" color="text.secondary">Trimestre actif</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'success.main' }}><ScheduleIcon /></Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'info.lighter' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4" fontWeight={700} color="info.main">1,250</Typography>
                  <Typography variant="body2" color="text.secondary">Élèves inscrits</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'info.main' }}><GroupIcon /></Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'warning.lighter' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4" fontWeight={700} color="warning.main">32</Typography>
                  <Typography variant="body2" color="text.secondary">Classes actives</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'warning.main' }}><CalendarIcon /></Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Années scolaires */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6" fontWeight={600}>Années Scolaires</Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpenDialog('annee-scol')}>
              Nouvelle année
            </Button>
          </Box>
        </CardContent>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Année</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Dates</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Périodes</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Statut</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mockAnneesScol.map((annee) => (
                <TableRow key={annee.id} hover>
                  <TableCell>
                    <Typography fontWeight={600}>{annee.libelle}</Typography>
                  </TableCell>
                  <TableCell>
                    {annee.date_debut} → {annee.date_fin}
                  </TableCell>
                  <TableCell>
                    <Chip label={`${annee.periodes} trimestres`} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    {annee.en_cours ? (
                      <Chip label="En cours" color="success" size="small" icon={<CheckIcon />} />
                    ) : annee.cloturee ? (
                      <Chip label="Clôturée" color="default" size="small" />
                    ) : (
                      <Chip label="Inactive" color="warning" size="small" />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                      {!annee.en_cours && !annee.cloturee && (
                        <Tooltip title="Activer">
                          <IconButton color="success" size="small">
                            <ActivateIcon />
                          </IconButton>
                        </Tooltip>
                      )}
                      {annee.en_cours && (
                        <Tooltip title="Clôturer">
                          <IconButton color="warning" size="small">
                            <CloseIcon />
                          </IconButton>
                        </Tooltip>
                      )}
                      <Tooltip title="Modifier">
                        <IconButton size="small">
                          <EditIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Gérer périodes">
                        <IconButton size="small" color="primary" onClick={() => handleOpenDialog('periodes', annee)}>
                          <ScheduleIcon />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Périodes (Trimestres) */}
      <Card>
        <CardContent sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6" fontWeight={600}>Périodes 2025-2026</Typography>
            <Button variant="outlined" startIcon={<AddIcon />} onClick={() => handleOpenDialog('periode')}>
              Ajouter période
            </Button>
          </Box>
        </CardContent>
        <List>
          {mockPeriodes.map((per, idx) => (
            <React.Fragment key={per.id}>
              <ListItem>
                <Avatar sx={{ bgcolor: per.cloturee ? 'grey.400' : 'secondary.main', mr: 2 }}>
                  T{per.numero}
                </Avatar>
                <ListItemText
                  primary={per.libelle}
                  secondary={`${per.date_debut} → ${per.date_fin}`}
                />
                <ListItemSecondaryAction>
                  <Stack direction="row" spacing={1} alignItems="center">
                    {per.cloturee ? (
                      <Chip label="Clôturé" size="small" color="default" />
                    ) : idx === 1 ? (
                      <>
                        <Chip label="En cours" size="small" color="success" />
                        <Button size="small" variant="outlined" color="warning">
                          Clôturer
                        </Button>
                      </>
                    ) : idx === 0 ? (
                      <Chip label="Clôturé" size="small" color="default" />
                    ) : (
                      <Chip label="À venir" size="small" color="info" />
                    )}
                    <IconButton size="small"><EditIcon /></IconButton>
                  </Stack>
                </ListItemSecondaryAction>
              </ListItem>
              {idx < mockPeriodes.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </List>
      </Card>
    </Box>
  );

  // ===================== PROMOTION TAB =====================
  const renderPromotionTab = () => (
    <Box>
      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={600}>Gestion des passages et promotions</Typography>
        <Typography variant="body2">
          Utilisez cet outil en fin d'année pour promouvoir automatiquement les élèves vers la classe supérieure 
          ou les inscrire dans un nouveau semestre (pour le supérieur).
        </Typography>
      </Alert>

      {/* Stepper for promotion process */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stepper activeStep={promotionStep} alternativeLabel>
            <Step>
              <StepLabel>Configuration</StepLabel>
            </Step>
            <Step>
              <StepLabel>Sélection élèves</StepLabel>
            </Step>
            <Step>
              <StepLabel>Validation</StepLabel>
            </Step>
            <Step>
              <StepLabel>Exécution</StepLabel>
            </Step>
          </Stepper>
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        {/* Secondaire - Promotion */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'secondary.lighter' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SchoolIcon color="secondary" />
                <Typography variant="h6" fontWeight={600}>Secondaire - Passage de classe</Typography>
              </Box>
            </CardContent>
            <CardContent>
              <Typography variant="body2" color="text.secondary" paragraph>
                Promouvoir les élèves qui ont réussi vers la classe supérieure.
              </Typography>
              
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Année scolaire source</InputLabel>
                <Select defaultValue="2024-2025" label="Année scolaire source">
                  <MenuItem value="2024-2025">2024-2025</MenuItem>
                  <MenuItem value="2023-2024">2023-2024</MenuItem>
                </Select>
              </FormControl>

              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Niveau/Classe source</InputLabel>
                <Select defaultValue="2nde" label="Niveau/Classe source">
                  <MenuItem value="6e">6ème</MenuItem>
                  <MenuItem value="5e">5ème</MenuItem>
                  <MenuItem value="4e">4ème</MenuItem>
                  <MenuItem value="3e">3ème</MenuItem>
                  <MenuItem value="2nde">2nde</MenuItem>
                  <MenuItem value="1ere">1ère</MenuItem>
                  <MenuItem value="tle">Terminale</MenuItem>
                </Select>
              </FormControl>

              <FormControlLabel
                control={<Switch defaultChecked />}
                label="Promotion automatique si moyenne ≥ 10"
              />
              <FormControlLabel
                control={<Switch />}
                label="Inclure les redoublements"
              />

              <Box sx={{ mt: 3 }}>
                <Button 
                  variant="contained" 
                  color="secondary" 
                  startIcon={<PromoteIcon />}
                  fullWidth
                  onClick={() => handleOpenDialog('preview-promotion')}
                >
                  Prévisualiser les promotions
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Supérieur - Inscription semestre */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'primary.lighter' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CalendarIcon color="primary" />
                <Typography variant="h6" fontWeight={600}>Supérieur - Nouveau semestre</Typography>
              </Box>
            </CardContent>
            <CardContent>
              <Typography variant="body2" color="text.secondary" paragraph>
                Inscrire les étudiants dans un nouveau semestre avec leurs matières selon leur parcours.
              </Typography>
              
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Semestre cible</InputLabel>
                <Select defaultValue="s2" label="Semestre cible">
                  <MenuItem value="s2">Semestre 2 (2025-2026)</MenuItem>
                  <MenuItem value="s3">Semestre 3 (2025-2026)</MenuItem>
                  <MenuItem value="s4">Semestre 4 (2025-2026)</MenuItem>
                </Select>
              </FormControl>

              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Formation / Parcours</InputLabel>
                <Select defaultValue="all" label="Formation / Parcours">
                  <MenuItem value="all">Toutes les formations</MenuItem>
                  <MenuItem value="info">Licence Informatique</MenuItem>
                  <MenuItem value="math">Licence Mathématiques</MenuItem>
                  <MenuItem value="gestion">Licence Gestion</MenuItem>
                </Select>
              </FormControl>

              <FormControlLabel
                control={<Switch defaultChecked />}
                label="Inscrire automatiquement aux matières du parcours"
              />
              <FormControlLabel
                control={<Switch defaultChecked />}
                label="Reporter les matières non validées"
              />

              <Box sx={{ mt: 3 }}>
                <Button 
                  variant="contained" 
                  color="primary" 
                  startIcon={<UpIcon />}
                  fullWidth
                  onClick={() => handleOpenDialog('preview-semestre')}
                >
                  Prévisualiser les inscriptions
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Preview table */}
      <Card sx={{ mt: 3 }}>
        <CardContent sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="h6" fontWeight={600}>Aperçu des élèves à promouvoir</Typography>
        </CardContent>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Élève</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Classe actuelle</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Moyenne</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Décision</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Classe suivante</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mockElevesPromo.map((eleve) => (
                <TableRow key={eleve.id} hover>
                  <TableCell>
                    <Typography fontWeight={500}>{eleve.nom}</Typography>
                  </TableCell>
                  <TableCell>{eleve.classe_actuelle}</TableCell>
                  <TableCell>
                    <Chip 
                      label={eleve.moyenne.toFixed(1) + '/20'} 
                      size="small" 
                      color={eleve.moyenne >= 10 ? 'success' : 'error'}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={eleve.decision === 'passage' ? 'Passage' : 'Redoublement'} 
                      size="small" 
                      color={eleve.decision === 'passage' ? 'success' : 'warning'}
                    />
                  </TableCell>
                  <TableCell>
                    {eleve.classe_suivante || '-'}
                  </TableCell>
                  <TableCell>
                    <Select size="small" defaultValue={eleve.decision} sx={{ minWidth: 130 }}>
                      <MenuItem value="passage">Passage</MenuItem>
                      <MenuItem value="redoublement">Redoublement</MenuItem>
                      <MenuItem value="exclusion">Exclusion</MenuItem>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <CardContent sx={{ borderTop: 1, borderColor: 'divider' }}>
          <Stack direction="row" spacing={2} justifyContent="flex-end">
            <Button variant="outlined">Annuler</Button>
            <Button variant="contained" color="success" startIcon={<CheckIcon />}>
              Valider et exécuter les promotions
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );

  // ===================== DIALOGS =====================
  const renderDialogs = () => (
    <>
      {/* Dialog: Nouvelle année universitaire */}
      <Dialog open={openDialog === 'annee-univ'} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Nouvelle Année Universitaire</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField fullWidth label="Libellé (ex: 2026-2027)" defaultValue="" />
            </Grid>
            <Grid item xs={6}>
              <TextField fullWidth label="Date de début" type="date" InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={6}>
              <TextField fullWidth label="Date de fin" type="date" InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel control={<Switch />} label="Activer immédiatement" />
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel control={<Switch defaultChecked />} label="Créer les semestres automatiquement (S1 et S2)" />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Annuler</Button>
          <Button variant="contained" onClick={handleCloseDialog}>Créer</Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: Activer année */}
      <Dialog open={openDialog === 'activer-annee'} onClose={handleCloseDialog} maxWidth="xs" fullWidth>
        <DialogTitle>Activer l'année universitaire</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mt: 1 }}>
            <Typography variant="body2">
              L'activation de <strong>{selectedItem?.libelle}</strong> désactivera automatiquement 
              l'année en cours. Cette action affectera les inscriptions et les opérations en cours.
            </Typography>
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Annuler</Button>
          <Button variant="contained" color="success" onClick={handleCloseDialog} startIcon={<ActivateIcon />}>
            Activer
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: Clôturer année */}
      <Dialog open={openDialog === 'cloturer-annee'} onClose={handleCloseDialog} maxWidth="xs" fullWidth>
        <DialogTitle>Clôturer l'année universitaire</DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mt: 1 }}>
            <Typography variant="body2">
              La clôture de <strong>{selectedItem?.libelle}</strong> est irréversible. 
              Assurez-vous que tous les semestres sont clôturés et que toutes les notes sont saisies.
            </Typography>
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Annuler</Button>
          <Button variant="contained" color="error" onClick={handleCloseDialog} startIcon={<CloseIcon />}>
            Clôturer définitivement
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: Clôturer semestre */}
      <Dialog open={openDialog === 'cloturer-semestre'} onClose={handleCloseDialog} maxWidth="xs" fullWidth>
        <DialogTitle>Clôturer le semestre</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mt: 1 }}>
            <Typography variant="body2">
              La clôture du <strong>Semestre {selectedItem?.numero}</strong> empêchera toute 
              modification des notes. Les jurys pourront délibérer.
            </Typography>
          </Alert>
          <FormControlLabel 
            control={<Switch />} 
            label="Activer automatiquement le semestre suivant" 
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Annuler</Button>
          <Button variant="contained" color="warning" onClick={handleCloseDialog}>
            Clôturer
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog: Nouveau semestre */}
      <Dialog open={openDialog === 'semestre'} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Nouveau Semestre</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={6}>
              <TextField fullWidth label="Numéro" type="number" defaultValue={3} />
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Type</InputLabel>
                <Select defaultValue="impair" label="Type">
                  <MenuItem value="impair">Impair (S1, S3, S5)</MenuItem>
                  <MenuItem value="pair">Pair (S2, S4, S6)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <TextField fullWidth label="Date de début" type="date" InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={6}>
              <TextField fullWidth label="Date de fin" type="date" InputLabelProps={{ shrink: true }} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Annuler</Button>
          <Button variant="contained" onClick={handleCloseDialog}>Créer</Button>
        </DialogActions>
      </Dialog>
    </>
  );

  return (
    <Box>
      <PageHeader
        title="Gestion des Années Académiques"
        subtitle="Années, semestres, périodes et promotions"
        actions={[
          { label: 'Actualiser', icon: <RefreshIcon />, variant: 'outlined', onClick: () => {} },
          { label: 'Paramètres', icon: <SettingsIcon />, variant: 'outlined', onClick: () => {} },
        ]}
      />

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab icon={<CalendarIcon />} iconPosition="start" label="Supérieur" />
          <Tab icon={<SchoolIcon />} iconPosition="start" label="Secondaire" />
          <Tab icon={<PromoteIcon />} iconPosition="start" label="Promotions" />
        </Tabs>
      </Box>

      {tabValue === 0 && renderSuperieurTab()}
      {tabValue === 1 && renderSecondaireTab()}
      {tabValue === 2 && renderPromotionTab()}

      {renderDialogs()}
    </Box>
  );
};

export default AnneesAcademiquesPage;
