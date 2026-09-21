import React, { useMemo, useState } from 'react';
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
  CircularProgress,
  Divider,
  TextField,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Stack,
} from '@mui/material';
import {
  Edit as EditIcon,
  Print as PrintIcon,
  Email as EmailIcon,
  ArrowBack as ArrowBackIcon,
  Phone as PhoneIcon,
  Cake as CakeIcon,
  LocationOn as LocationIcon,
  Public as PublicIcon,
} from '@mui/icons-material';
import { PageHeader, SISDataTable } from '../../components/common';
import {
  useAjouterMatiereIndividuelleEtudiant,
  useECUEs,
  useEtudiant,
  useEtudiantMatieresIndividuelles,
  useInscriptions,
  useNotes,
  useRetirerMatiereIndividuelleEtudiant,
  useSemestres,
} from '../../services/api';

const emptyForm = {
  inscription_admin: '',
  semestre_cible: '',
  ecue: '',
  obligatoire: true,
  commentaire: '',
};

const EtudiantDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tabValue, setTabValue] = useState(0);
  const [formData, setFormData] = useState(emptyForm);

  const { data: etudiant, isLoading } = useEtudiant(id);
  const { data: inscriptions = [] } = useInscriptions({ etudiant: id });
  const { data: notes = [] } = useNotes({ etudiant: id });
  const { data: semestres = [] } = useSemestres();
  const ecueParams = formData.semestre_cible ? { ue__semestre: formData.semestre_cible } : {};
  const { data: ecues = [] } = useECUEs(ecueParams);
  const { data: matieresIndividuelles = [] } = useEtudiantMatieresIndividuelles(id);
  const ajouterMatiere = useAjouterMatiereIndividuelleEtudiant();
  const retirerMatiere = useRetirerMatiereIndividuelleEtudiant();

  const user = etudiant?.user || {};
  const nomComplet = `${user.first_name || ''} ${user.last_name || ''}`.trim() || etudiant?.matricule || 'Étudiant';

  const getInitials = () => `${(user.last_name || '')[0] || ''}${(user.first_name || '')[0] || ''}`;

  const inscriptionColumns = [
    { Header: 'Année', accessor: 'annee_universitaire_libelle' },
    { Header: 'Formation', accessor: 'formation_nom' },
    { Header: 'Statut', accessor: 'statut_display' },
    { Header: 'Régime', accessor: 'regime' },
  ];

  const notesColumns = [
    { Header: 'Évaluation', accessor: 'evaluation_titre' },
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    {
      Header: 'Note',
      accessor: 'valeur',
      Cell: ({ value }) => (
        <Chip
          label={value !== undefined && value !== null ? `${value}/20` : '-'}
          size="small"
          color={value >= 10 ? 'success' : value !== undefined && value !== null ? 'error' : 'default'}
        />
      ),
    },
    { Header: 'Statut', accessor: 'statut_display' },
  ];

  const matieresColumns = [
    { Header: 'Semestre cible', accessor: 'semestre_cible_libelle' },
    { Header: 'ECUE', accessor: 'ecue_nom' },
    { Header: 'UE', accessor: 'ue_nom' },
    { Header: 'Semestre source', accessor: 'source_semestre' },
  ];

  const inscriptionOptions = useMemo(
    () => inscriptions.filter((item) => item?.id),
    [inscriptions],
  );
  const semestreOptions = useMemo(
    () => semestres.filter((item) => item?.id),
    [semestres],
  );
  const ecueOptions = useMemo(
    () => ecues.filter((item) => item?.id),
    [ecues],
  );

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!formData.inscription_admin || !formData.semestre_cible || !formData.ecue) {
      return;
    }
    await ajouterMatiere.mutateAsync({
      etudiantId: id,
      data: {
        inscription_admin: Number(formData.inscription_admin),
        semestre_cible: Number(formData.semestre_cible),
        ecue: Number(formData.ecue),
        obligatoire: formData.obligatoire,
        commentaire: formData.commentaire,
      },
    });
    setFormData(emptyForm);
  };

  const handleRemove = async (affectationId) => {
    await retirerMatiere.mutateAsync({ etudiantId: id, affectationId });
  };

  const InfoRow = ({ icon, label, value }) => (
    <Box sx={{ display: 'flex', alignItems: 'center', py: 1 }}>
      {icon}
      <Box sx={{ ml: 2 }}>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography variant="body2">{value || 'Non renseigné'}</Typography>
      </Box>
    </Box>
  );

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

  return (
    <Box>
      <PageHeader
        title={nomComplet}
        subtitle={`Matricule: ${etudiant.matricule || 'N/A'}`}
        showBack
        breadcrumbs={[
          { label: 'Étudiants', path: '/superieur/etudiants' },
          { label: nomComplet },
        ]}
        actions={[
          { label: 'Imprimer', icon: <PrintIcon />, variant: 'outlined', onClick: () => window.print() },
          { label: 'Email', icon: <EmailIcon />, variant: 'outlined', onClick: () => { window.location.href = `mailto:${user.email || etudiant.email_personnel || ''}`; } },
          { label: 'Modifier', icon: <EditIcon />, variant: 'contained', onClick: () => navigate('edit') },
        ]}
      />

      <Grid container spacing={3}>
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
                  mb: 2,
                }}
              >
                {getInitials()}
              </Avatar>
              <Typography variant="h5" fontWeight={600}>
                {nomComplet}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {etudiant.annee_universitaire_libelle || 'Année universitaire non définie'}
              </Typography>
              <Chip
                label={etudiant.statut_display || 'Inconnu'}
                color={etudiant.statut === 'inscrit' ? 'success' : 'default'}
                size="small"
                sx={{ mt: 1 }}
              />
            </CardContent>
            <Divider />
            <CardContent>
              <InfoRow icon={<EmailIcon color="action" />} label="Email" value={user.email || etudiant.email_personnel} />
              <InfoRow icon={<PhoneIcon color="action" />} label="Téléphone" value={etudiant.telephone} />
              <InfoRow icon={<CakeIcon color="action" />} label="Date de naissance" value={etudiant.date_naissance} />
              <InfoRow icon={<LocationIcon color="action" />} label="Lieu de naissance" value={etudiant.lieu_naissance} />
              <InfoRow icon={<PublicIcon color="action" />} label="Nationalité" value={etudiant.nationalite} />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          <Card>
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs value={tabValue} onChange={(_event, value) => setTabValue(value)}>
                <Tab label="Inscriptions" />
                <Tab label="Notes" />
                <Tab label="Matières individualisées" />
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
                <Stack component="form" spacing={2} onSubmit={handleSubmit} sx={{ mb: 3 }}>
                  <TextField
                    select
                    label="Inscription administrative"
                    value={formData.inscription_admin}
                    onChange={(event) => setFormData((current) => ({ ...current, inscription_admin: event.target.value }))}
                    required
                  >
                    {inscriptionOptions.map((inscription) => (
                      <MenuItem key={inscription.id} value={inscription.id}>
                        {`${inscription.formation_nom || 'Formation'} — ${inscription.annee_universitaire_libelle || inscription.annee_universitaire}`}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    select
                    label="Semestre cible"
                    value={formData.semestre_cible}
                    onChange={(event) => setFormData((current) => ({ ...current, semestre_cible: event.target.value, ecue: '' }))}
                    required
                  >
                    {semestreOptions.map((semestre) => (
                      <MenuItem key={semestre.id} value={semestre.id}>
                        {semestre.libelle || `Semestre ${semestre.numero}`}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    select
                    label="ECUE"
                    value={formData.ecue}
                    onChange={(event) => setFormData((current) => ({ ...current, ecue: event.target.value }))}
                    required
                  >
                    {ecueOptions.map((ecue) => (
                      <MenuItem key={ecue.id} value={ecue.id}>
                        {`${ecue.code || ''} ${ecue.nom || ''}`.trim()}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    label="Commentaire"
                    multiline
                    minRows={2}
                    value={formData.commentaire}
                    onChange={(event) => setFormData((current) => ({ ...current, commentaire: event.target.value }))}
                  />
                  <FormControlLabel
                    control={(
                      <Checkbox
                        checked={formData.obligatoire}
                        onChange={(event) => setFormData((current) => ({ ...current, obligatoire: event.target.checked }))}
                      />
                    )}
                    label="ECUE obligatoire"
                  />
                  <Box>
                    <Button type="submit" variant="contained" disabled={ajouterMatiere.isPending}>
                      {ajouterMatiere.isPending ? 'Ajout...' : 'Ajouter l’ECUE'}
                    </Button>
                  </Box>
                </Stack>

                <SISDataTable
                  title="ECUE personnalisés"
                  data={matieresIndividuelles}
                  columns={matieresColumns}
                  searchable={false}
                  exportable={false}
                  pageSize={5}
                  emptyMessage="Aucune matière individualisée"
                />

                <Stack spacing={1.5} sx={{ mt: 2 }}>
                  {matieresIndividuelles.map((affectation) => (
                    <Box
                      key={affectation.id}
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: 1,
                        p: 1.5,
                      }}
                    >
                      <Box>
                        <Typography fontWeight={600}>{affectation.ecue_nom}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {`${affectation.semestre_cible_libelle} • source: ${affectation.source_semestre}`}
                        </Typography>
                      </Box>
                      <Button
                        variant="outlined"
                        color="error"
                        onClick={() => handleRemove(affectation.id)}
                        disabled={retirerMatiere.isPending}
                      >
                        Retirer
                      </Button>
                    </Box>
                  ))}
                </Stack>
              </Box>
            )}
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default EtudiantDetailPage;
