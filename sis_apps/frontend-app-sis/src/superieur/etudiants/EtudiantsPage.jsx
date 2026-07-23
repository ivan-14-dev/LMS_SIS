import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  InputAdornment,
  IconButton,
  Chip,
  Avatar,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Paper,
  Tooltip,
  Skeleton,
  LinearProgress,
  Alert,
  Snackbar,
  Fab,
  useTheme,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  FilterList as FilterIcon,
  MoreVert as MoreVertIcon,
  Download as DownloadIcon,
  Upload as UploadIcon,
  Refresh as RefreshIcon,
  Person as PersonIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as VisibilityIcon,
  School as SchoolIcon,
  Print as PrintIcon,
} from '@mui/icons-material';
import { useEtudiants, useCreateEtudiant } from '../../services/api';

const getStatusColor = (status) => {
  const colors = {
    actif: 'success',
    diplome: 'primary',
    suspendu: 'warning',
    abandonne: 'error',
  };
  return colors[status] || 'default';
};

const getStatusLabel = (status) => {
  const labels = {
    actif: 'Actif',
    diplome: 'Diplômé',
    suspendu: 'Suspendu',
    abandonne: 'Abandonné',
  };
  return labels[status] || status;
};

const EtudiantsPage = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [searchTerm, setSearchTerm] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [filters, setFilters] = useState({});
  const [anchorEl, setAnchorEl] = useState(null);
  const [selectedRow, setSelectedRow] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  
  const { data: etudiants = [], isLoading, refetch } = useEtudiants(filters);
  const createMutation = useCreateEtudiant();

  // Form state
  const [formData, setFormData] = useState({
    nom: '',
    prenom: '',
    email: '',
    date_naissance: '',
    sexe: 'M',
    telephone: '',
    adresse: '',
  });

  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
    setPage(0);
  };

  const filteredData = etudiants.filter(etudiant => {
    const searchLower = searchTerm.toLowerCase();
    return (
      etudiant.matricule?.toLowerCase().includes(searchLower) ||
      etudiant.nom?.toLowerCase().includes(searchLower) ||
      etudiant.prenom?.toLowerCase().includes(searchLower) ||
      etudiant.email?.toLowerCase().includes(searchLower)
    );
  });

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleMenuOpen = (event, row) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
    setSelectedRow(row);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedRow(null);
  };

  const handleRowClick = (row) => {
    navigate(`/superieur/etudiants/${row.id}`);
  };

  const handleFormChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async () => {
    try {
      await createMutation.mutateAsync(formData);
      setShowModal(false);
      setFormData({ nom: '', prenom: '', email: '', date_naissance: '', sexe: 'M', telephone: '', adresse: '' });
      setSnackbar({ open: true, message: 'Étudiant créé avec succès !', severity: 'success' });
    } catch (error) {
      setSnackbar({ open: true, message: 'Erreur lors de la création', severity: 'error' });
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Gestion des Étudiants
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {filteredData.length} étudiants enregistrés
          </Typography>
        </Box>
        <Button 
          variant="contained" 
          startIcon={<AddIcon />}
          onClick={() => setShowModal(true)}
          size="large"
        >
          Nouvel étudiant
        </Button>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'primary.light', color: 'primary.contrastText' }}>
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Avatar sx={{ bgcolor: 'primary.main', width: 48, height: 48 }}>
                <PersonIcon />
              </Avatar>
              <Box>
                <Typography variant="h5" fontWeight={700}>{etudiants.length}</Typography>
                <Typography variant="body2">Total étudiants</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'success.light', color: 'success.contrastText' }}>
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Avatar sx={{ bgcolor: 'success.main', width: 48, height: 48 }}>
                <SchoolIcon />
              </Avatar>
              <Box>
                <Typography variant="h5" fontWeight={700}>
                  {etudiants.filter(e => e.statut === 'actif').length}
                </Typography>
                <Typography variant="body2">Actifs</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'info.light', color: 'info.contrastText' }}>
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Avatar sx={{ bgcolor: 'info.main', width: 48, height: 48 }}>
                <SchoolIcon />
              </Avatar>
              <Box>
                <Typography variant="h5" fontWeight={700}>
                  {etudiants.filter(e => e.statut === 'diplome').length}
                </Typography>
                <Typography variant="body2">Diplômés</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'warning.light', color: 'warning.contrastText' }}>
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Avatar sx={{ bgcolor: 'warning.main', width: 48, height: 48 }}>
                <PersonIcon />
              </Avatar>
              <Box>
                <Typography variant="h5" fontWeight={700}>
                  {new Date().getFullYear()}
                </Typography>
                <Typography variant="body2">Année en cours</Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters & Actions Bar */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
            <TextField
              placeholder="Rechercher un étudiant..."
              value={searchTerm}
              onChange={handleSearchChange}
              size="small"
              sx={{ minWidth: 300, flexGrow: 1 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon color="action" />
                  </InputAdornment>
                ),
              }}
            />
            <Button variant="outlined" startIcon={<FilterIcon />}>
              Filtres
            </Button>
            <Button variant="outlined" startIcon={<DownloadIcon />}>
              Exporter
            </Button>
            <Tooltip title="Actualiser">
              <IconButton onClick={() => refetch()}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </CardContent>
      </Card>

      {/* Data Table */}
      <Card>
        {isLoading && <LinearProgress />}
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Matricule</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Nom complet</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Email</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Formation</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Niveau</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Statut</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Inscription</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50', width: 60 }}></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                [...Array(5)].map((_, index) => (
                  <TableRow key={index}>
                    {[...Array(8)].map((_, cellIndex) => (
                      <TableCell key={cellIndex}>
                        <Skeleton variant="text" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filteredData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 6 }}>
                    <Typography variant="body1" color="text.secondary">
                      Aucun étudiant trouvé
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredData
                  .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                  .map((etudiant) => (
                    <TableRow 
                      key={etudiant.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleRowClick(etudiant)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={600} color="primary.main">
                          {etudiant.matricule}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                          <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.light', color: 'primary.main', fontSize: '0.875rem' }}>
                            {etudiant.prenom?.[0]}{etudiant.nom?.[0]}
                          </Avatar>
                          <Typography variant="body2">
                            {etudiant.prenom} {etudiant.nom}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {etudiant.email}
                        </Typography>
                      </TableCell>
                      <TableCell>{etudiant.formation_nom || '-'}</TableCell>
                      <TableCell>
                        <Chip 
                          label={etudiant.niveau || '-'} 
                          size="small" 
                          variant="outlined" 
                        />
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={getStatusLabel(etudiant.statut)} 
                          size="small" 
                          color={getStatusColor(etudiant.statut)}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {etudiant.date_inscription || '-'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <IconButton size="small" onClick={(e) => handleMenuOpen(e, etudiant)}>
                          <MoreVertIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={filteredData.length}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[5, 10, 25, 50]}
          labelRowsPerPage="Lignes par page:"
          labelDisplayedRows={({ from, to, count }) => `${from}-${to} sur ${count}`}
        />
      </Card>

      {/* Row Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => { handleMenuClose(); selectedRow && navigate(`/superieur/etudiants/${selectedRow.id}`); }}>
          <VisibilityIcon fontSize="small" sx={{ mr: 1 }} /> Voir détails
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <EditIcon fontSize="small" sx={{ mr: 1 }} /> Modifier
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <PrintIcon fontSize="small" sx={{ mr: 1 }} /> Imprimer carte
        </MenuItem>
        <MenuItem onClick={handleMenuClose} sx={{ color: 'error.main' }}>
          <DeleteIcon fontSize="small" sx={{ mr: 1 }} /> Supprimer
        </MenuItem>
      </Menu>

      {/* Create Dialog */}
      <Dialog 
        open={showModal} 
        onClose={() => setShowModal(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 600, borderBottom: 1, borderColor: 'divider' }}>
          Nouvel étudiant
        </DialogTitle>
        <DialogContent sx={{ pt: 3 }}>
          <Grid container spacing={3} sx={{ mt: 0 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Nom"
                name="nom"
                value={formData.nom}
                onChange={handleFormChange}
                fullWidth
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Prénom"
                name="prenom"
                value={formData.prenom}
                onChange={handleFormChange}
                fullWidth
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleFormChange}
                fullWidth
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Téléphone"
                name="telephone"
                value={formData.telephone}
                onChange={handleFormChange}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Date de naissance"
                name="date_naissance"
                type="date"
                value={formData.date_naissance}
                onChange={handleFormChange}
                fullWidth
                required
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Sexe</InputLabel>
                <Select
                  name="sexe"
                  value={formData.sexe}
                  onChange={handleFormChange}
                  label="Sexe"
                >
                  <MenuItem value="M">Masculin</MenuItem>
                  <MenuItem value="F">Féminin</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Adresse"
                name="adresse"
                value={formData.adresse}
                onChange={handleFormChange}
                fullWidth
                multiline
                rows={2}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2, borderTop: 1, borderColor: 'divider' }}>
          <Button onClick={() => setShowModal(false)} color="inherit">
            Annuler
          </Button>
          <Button 
            onClick={handleSubmit} 
            variant="contained"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Création...' : 'Créer l\'étudiant'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={() => setSnackbar({ ...snackbar, open: false })} 
          severity={snackbar.severity}
          variant="filled"
        >
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* Floating Action Button for mobile */}
      <Fab 
        color="primary" 
        sx={{ 
          position: 'fixed', 
          bottom: 24, 
          right: 24,
          display: { xs: 'flex', md: 'none' }
        }}
        onClick={() => setShowModal(true)}
      >
        <AddIcon />
      </Fab>
    </Box>
  );
};

export default EtudiantsPage;
