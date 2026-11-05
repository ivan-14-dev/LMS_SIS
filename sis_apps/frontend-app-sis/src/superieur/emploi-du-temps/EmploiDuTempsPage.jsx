import React, { useState } from 'react';
import {
  Alert, Box, Button, MenuItem, Paper, Stack, Tab, Tabs, TextField, Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../../components/common';
import ResourceManager from '../../components/common/ResourceManager';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { fetchApi } from '../../services/api';
import { apiErrorMessage, fetchAllResourcePages, resourceUrl } from '../../services/resources';

const days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];
const choices = values => values.map(value => ({ value, label: value }));
const references = {
  formation: { resource: 'formations/formations', label: 'Formation', labelField: 'nom' },
  enseignant: { resource: 'enseignants', label: 'Enseignant', labelField: 'full_name' },
  salle: { resource: 'edt/salles', label: 'Salle', labelField: 'nom' },
};

const EmploiDuTempsPage = () => {
  const [tab, setTab] = useState('planning');
  const [view, setView] = useState('formation');
  const [selected, setSelected] = useState('');
  const [semester, setSemester] = useState('');
  const { data: capabilities } = useCapabilities('superieur');
  const manager = capabilities?.permissions?.some(value => ['*', 'emplois_du_temps.change_creneaucours'].includes(value))
    || ['scolarite', 'directeur_etudes', 'responsable_formation', 'doyen'].includes(capabilities?.role);
  const reference = references[view];
  const options = useQuery({
    queryKey: ['reference', resourceUrl('superieur', reference.resource)],
    queryFn: () => fetchAllResourcePages(resourceUrl('superieur', reference.resource)),
  });
  const semesters = useQuery({
    queryKey: ['reference', resourceUrl('superieur', 'etablissement/semestres')],
    queryFn: () => fetchAllResourcePages(resourceUrl('superieur', 'etablissement/semestres')),
  });
  const planning = useQuery({
    queryKey: ['resource', 'planning', view, selected, semester],
    queryFn: () => fetchApi(
      `${resourceUrl('superieur', 'edt/creneaux-cours')}par_${view}/?${view}_id=${selected}&semestre_id=${semester}`,
    ),
    enabled: Boolean(selected && semester),
  });
  const error = options.error || semesters.error || planning.error;
  return (
    <Box>
      <PageHeader title="Emploi du temps" subtitle="Créneaux et réservations de salles" />
      <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" scrollButtons="auto" sx={{ mb: 3 }}>
        <Tab value="planning" label="Emploi du temps" />
        <Tab value="creneaux" label="Créneaux" />
        <Tab value="reservations" label="Réservations" />
        <Tab value="salles" label="Salles" />
        {manager && <Tab value="horaires" label="Horaires types" />}
      </Tabs>
      {tab === 'planning' && (
        <Box>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }}>
            <TextField select label="Vue par" value={view} onChange={event => { setView(event.target.value); setSelected(''); }} sx={{ minWidth: 150 }}>
              {Object.entries(references).map(([key, item]) => <MenuItem key={key} value={key}>{item.label}</MenuItem>)}
            </TextField>
            <TextField
              select
              label={reference.label}
              value={selected}
              onChange={event => setSelected(event.target.value)}
              sx={{ minWidth: 220 }}
            >
              <MenuItem value="">Sélectionner</MenuItem>
              {(options.data || []).map(item => (
                <MenuItem key={item.id} value={item.id}>
                  {item[reference.labelField] || item.nom_complet || item.nom || item.id}
                </MenuItem>
              ))}
            </TextField>
            <TextField select label="Semestre" value={semester} onChange={event => setSemester(event.target.value)} sx={{ minWidth: 220 }}>
              <MenuItem value="">Sélectionner</MenuItem>
              {(semesters.data || []).map(item => <MenuItem key={item.id} value={item.id}>{item.annee_libelle} — {item.libelle || `Semestre ${item.numero}`}</MenuItem>)}
            </TextField>
            <Button onClick={() => window.print()} disabled={!planning.data}>Imprimer</Button>
          </Stack>
          {error && <Alert severity="error">{apiErrorMessage(error)}</Alert>}
          {!selected || !semester ? <Alert severity="info">Sélectionnez une vue et un semestre.</Alert> : (
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>
              {days.map((day, index) => (
                <Paper
                  key={day}
                  component="section"
                  variant="outlined"
                  sx={{ p: 2, minWidth: 0 }}
                >
                  <Typography variant="h6" component="h2">{day}</Typography>
                  {(planning.data?.emploi_du_temps?.[index] || []).map(item => (
                    <Box
                      key={item.id}
                      sx={{
                        borderTop: 1, borderColor: 'divider', mt: 1, pt: 1,
                      }}
                    >
                      <Typography variant="subtitle2" component="p">{item.horaire} — {item.ecue_nom}</Typography>
                      <Typography variant="body2">{item.type_display} · {item.salle_code} · {item.enseignant_nom}</Typography>
                    </Box>
                  ))}
                  {!planning.data?.emploi_du_temps?.[index]?.length && <Typography color="text.secondary">{planning.isFetching ? 'Chargement…' : 'Aucun cours.'}</Typography>}
                </Paper>
              ))}
            </Box>
          )}
        </Box>
      )}
      {tab === 'creneaux' && (
        <ResourceManager
          variant="superieur"
          resource="edt/creneaux-cours"
          headingLevel={2}
          title="Créneaux de cours"
          allowCreate={Boolean(manager)}
          allowEdit={Boolean(manager)}
          columns={[
            { Header: 'Jour', accessor: 'jour_display' }, { Header: 'Horaire', accessor: 'horaire' },
            { Header: 'ECUE', accessor: 'ecue_nom' }, { Header: 'Enseignant', accessor: 'enseignant_nom' },
            { Header: 'Salle', accessor: 'salle_code' },
          ]}
          fields={[
            {
              name: 'semestre', label: 'Semestre', resource: 'etablissement/semestres', labelField: 'libelle', required: true,
            },
            {
              name: 'formation', label: 'Formation', resource: 'formations/formations', required: true,
            },
            {
              name: 'ecue', label: 'ECUE', resource: 'ue-ecue/ecues', required: true,
            },
            {
              name: 'enseignant', label: 'Enseignant', resource: 'enseignants', labelField: 'full_name',
            },
            { name: 'salle', label: 'Salle', resource: 'edt/salles' },
            {
              name: 'jour', label: 'Jour', type: 'number', choices: days.map((label, value) => ({ value, label })), required: true,
            },
            {
              name: 'creneau_horaire', label: 'Horaire', resource: 'edt/creneaux-horaires', labelField: 'display', required: true,
            },
            {
              name: 'type_cours', label: 'Type', choices: choices(['CM', 'TD', 'TP', 'projet', 'examen', 'autre']), required: true, defaultValue: 'CM',
            },
            { name: 'groupe', label: 'Groupe' },
          ]}
        />
      )}
      {tab === 'reservations' && (
        <ResourceManager
          variant="superieur"
          resource="edt/reservations"
          headingLevel={2}
          title="Réservations de salles"
          searchable={false}
          allowEdit={false}
          columns={[
            { Header: 'Salle', accessor: 'salle_code' }, { Header: 'Date', accessor: 'date' },
            { Header: 'Début', accessor: 'heure_debut' }, { Header: 'Fin', accessor: 'heure_fin' },
            { Header: 'Statut', accessor: 'statut_display' },
          ]}
          fields={[
            {
              name: 'salle', label: 'Salle', resource: 'edt/salles', required: true,
            },
            {
              name: 'date', label: 'Date', type: 'date', required: true,
            },
            {
              name: 'heure_debut', label: 'Début', type: 'time', required: true,
            },
            {
              name: 'heure_fin', label: 'Fin', type: 'time', required: true,
            },
            {
              name: 'motif', label: 'Motif', choices: choices(['cours_rattrapage', 'examen', 'reunion', 'soutenance', 'evenement', 'autre']), required: true,
            },
            { name: 'description', label: 'Description', multiline: true },
          ]}
          actions={manager ? [{
            label: 'Décider',
            endpoint: 'valider',
            statuses: ['en_attente'],
            fields: [
              {
                name: 'action', label: 'Décision', choices: choices(['confirmer', 'refuser']), required: true,
              },
              { name: 'motif_refus', label: 'Motif de refus', multiline: true },
            ],
          }] : []}
        />
      )}
      {tab === 'salles' && (
        <ResourceManager
          variant="superieur"
          resource="edt/salles"
          headingLevel={2}
          title="Salles"
          columns={[{ Header: 'Code', accessor: 'code' }, { Header: 'Nom', accessor: 'nom' }, { Header: 'Capacité', accessor: 'capacite' }]}
        />
      )}
      {tab === 'horaires' && manager && (
        <ResourceManager
          variant="superieur"
          resource="edt/creneaux-horaires"
          headingLevel={2}
          title="Horaires types"
          searchable={false}
          columns={[{ Header: 'Horaire', accessor: 'display' }, { Header: 'Ordre', accessor: 'ordre' }]}
          fields={[
            {
              name: 'heure_debut', label: 'Début', type: 'time', required: true,
            },
            {
              name: 'heure_fin', label: 'Fin', type: 'time', required: true,
            },
            {
              name: 'ordre', label: 'Ordre', type: 'number', required: true,
            },
          ]}
        />
      )}
    </Box>
  );
};

export default EmploiDuTempsPage;
