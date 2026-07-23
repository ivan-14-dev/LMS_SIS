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
  Tooltip,
  Skeleton,
  LinearProgress,
  Alert,
  Snackbar,
  Fab,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  FilterList as FilterIcon,
  MoreVert as MoreVertIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  Person as PersonIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as VisibilityIcon,
  School as SchoolIcon,
  Print as PrintIcon,
} from '@mui/icons-material';
import { useEleves, useCreateEleve } from '../../services/api';

const getStatusColor = (status) => {
  const colors = {
    actif: 'success',
    inactif: 'error',
    transfere: 'warning',
  };
  return colors[status] || 'default';
};

const ElevesPage = () => {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [anchorEl, setAnchorEl] = useState(null);
  const [selectedRow, setSelectedRow] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  
  const { data: eleves = [], isLoading, refetch } = useEleves();
  const createMutation = useCreateEleve ? useCreateEleve() : { mutateAsync: async () => {}, isPending: false };

  const [formData, setFormData] = useState({
    nom: '',
    prenom: '',
    date_naissance: '',
    sexe: 'M',
    classe_id: '',
  });

  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
    setPage(0);
  };

  const filteredData = eleves.filter(eleve => {
    const searchLower = searchTerm.toLowerCase();
    return (
      eleve.matricule?.toLowerCase().includes(searchLower) ||
      eleve.nom?.toLowerCase().includes(searchLower) ||
      eleve.prenom?.toLowerCase().includes(searchLower)
    );
  });

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
    navigate(`/secondaire/eleves/${row.id}`);
  };

  const handleFormChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async () => {
    try {
      await createMutation.mutateAsync(formData);
      setShowModal(false);
      setFormData({ nom: '', prenom: '', date_naissance: '', sexe: 'M', classe_id: '' });
      setSnackbar({ open: true, message: 'Élève créé avec succès !', severity: 'success' });
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
            Gestion des Élèves
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {filteredData.length} élèves enregistrés
          </Typography>
        </Box>
        <Button 
          variant="contained" 
          startIcon={<AddIcon />}
          onClick={() => setShowModal(true)}
          size="large"
        >
          Nouvel élève
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
                <Typography variant="h5" fontWeight={700}>{eleves.length}</Typography>
                <Typography variant="body2">Total élèves</Typography>
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
                  {eleves.filter(e => e.statut === 'actif').length}
                </Typography>
                <Typography variant="body2">Actifs</Typography>
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
              placeholder="Rechercher un élève..."
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
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Classe</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Date naissance</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50' }}>Statut</TableCell>
                <TableCell sx={{ fontWeight: 600, bgcolor: 'grey.50', width: 60 }}></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                [...Array(5)].map((_, index) => (
                  <TableRow key={index}>
                    {[...Array(6)].map((_, cellIndex) => (
                      <TableCell key={cellIndex}>
                        <Skeleton variant="text" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filteredData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                    <Typography variant="body1" color="text.secondary">
                      Aucun élève trouvé
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredData
                  .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                  .map((eleve) => (
                    <TableRow 
                      key={eleve.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleRowClick(eleve)}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={600} color="primary.main">
                          {eleve.matricule}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                          <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.light', color: 'primary.main', fontSize: '0.875rem' }}>
                            {eleve.prenom?.[0]}{eleve.nom?.[0]}
                          </Avatar>
                          <Typography variant="body2">
                            {eleve.prenom} {eleve.nom}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip label={eleve.classe_nom || '-'} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>{eleve.date_naissance || '-'}</TableCell>
                      <TableCell>
                        <Chip 
                          label={eleve.statut || 'actif'} 
                          size="small" 
                          color={getStatusColor(eleve.statut)}
                        />
                      </TableCell>
                      <TableCell>
                        <IconButton size="small" onClick={(e) => handleMenuOpen(e, eleve)}>
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
          onPageChange={(e, newPage) => setPage(newPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
          rowsPerPageOptions={[5, 10, 25, 50]}
          labelRowsPerPage="Lignes par page:"
          labelDisplayedRows={({ from, to, count }) => `${from}-${to} sur ${count}`}
        />
      </Card>

      {/* Row Actions Menu */}
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}>
        <MenuItem onClick={() => { handleMenuClose(); selectedRow && navigate(`/secondaire/eleves/${selectedRow.id}`); }}>
          <VisibilityIcon fontSize="small" sx={{ mr: 1 }} /> Voir détails
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <EditIcon fontSize="small" sx={{ mr: 1 }} /> Modifier
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <PrintIcon fontSize="small" sx={{ mr: 1 }} /> Imprimer fiche
        </MenuItem>
        <MenuItem onClick={handleMenuClose} sx={{ color: 'error.main' }}>
          <DeleteIcon fontSize="small" sx={{ mr: 1 }} /> Supprimer
        </MenuItem>
      </Menu>

      {/* Create Dialog */}
      <Dialog open={showModal} onClose={() => setShowModal(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 600, borderBottom: 1, borderColor: 'divider' }}>
          Nouvel élève
        </DialogTitle>
        <DialogContent sx={{ pt: 3 }}>
          <Grid container spacing={3} sx={{ mt: 0 }}>
            <Grid item xs={12} sm={6}>
              <TextField label="Nom" name="nom" value={formData.nom} onChange={handleFormChange} fullWidth required />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField label="Prénom" name="prenom" value={formData.prenom} onChange={handleFormChange} fullWidth required />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField label="Date de naissance" name="date_naissance" type="date" value={formData.date_naissance} onChange={handleFormChange} fullWidth required InputLabelProps={{ shrink: true }} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Sexe</InputLabel>
                <Select name="sexe" value={formData.sexe} onChange={handleFormChange} label="Sexe">
                  <MenuItem value="M">Masculin</MenuItem>
                  <MenuItem value="F">Féminin</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2, borderTop: 1, borderColor: 'divider' }}>
          <Button onClick={() => setShowModal(false)} color="inherit">Annuler</Button>
          <Button onClick={handleSubmit} variant="contained" disabled={createMutation.isPending}>
            {createMutation.isPending ? 'Création...' : 'Créer'}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={() => setSnackbar({ ...snackbar, open: false })} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity} variant="filled">{snackbar.message}</Alert>
      </Snackbar>

      <Fab color="primary" sx={{ position: 'fixed', bottom: 24, right: 24, display: { xs: 'flex', md: 'none' } }} onClick={() => setShowModal(true)}>
        <AddIcon />
      </Fab>
    </Box>
  );
};

export default ElevesPage;
