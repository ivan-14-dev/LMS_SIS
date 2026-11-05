import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Stack, Tab, Tabs,
} from '@mui/material';
import { PageHeader, WorkflowHistoryPanel } from '../../components/common';
import ResourceManager from '../../components/common/ResourceManager';
import { useFormation } from '../../services/api';
import { apiErrorMessage } from '../../services/resources';

const FormationDetailPage = () => {
  const { id } = useParams();
  const { data: formation, isLoading, error } = useFormation(id);
  const [tab, setTab] = useState('structure');
  const [maquette, setMaquette] = useState(null);
  const [ue, setUE] = useState(null);
  if (isLoading) { return <p>Chargement de la formation…</p>; }
  if (error) { return <Alert severity="error">{apiErrorMessage(error)}</Alert>; }
  if (!formation) { return <Alert severity="error">Formation non trouvée.</Alert>; }
  return (
    <Box>
      <PageHeader title={formation.nom} subtitle={`Code : ${formation.code}`} showBack />
      <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" scrollButtons="auto" sx={{ mb: 3 }}>
        <Tab value="information" label="Informations" />
        <Tab value="structure" label="Maquettes et UE / ECUE" />
        <Tab value="parcours" label="Parcours" />
        <Tab value="etudiants" label="Étudiants" />
        <Tab value="emploi" label="Emploi du temps" />
        <Tab value="historique" label="Historique" />
      </Tabs>
      {tab === 'information' && (
        <ResourceManager
          variant="superieur"
          resource="formations/formations"
          headingLevel={2}
          title="Informations de la formation"
          filters={{ id }}
          allowCreate={false}
          columns={[
            { Header: 'Code', accessor: 'code' }, { Header: 'Nom', accessor: 'nom' },
            { Header: 'Crédits', accessor: 'credits_total' }, { Header: 'Durée', accessor: 'duree_annees' },
          ]}
          fields={[
            { name: 'code', label: 'Code', required: true },
            { name: 'nom', label: 'Nom', required: true },
            { name: 'description', label: 'Description', multiline: true },
            {
              name: 'duree_annees', label: 'Durée (années)', type: 'number', required: true,
            },
            {
              name: 'nb_semestres', label: 'Nombre de semestres', type: 'number', required: true,
            },
            {
              name: 'credits_total', label: 'Crédits', type: 'number', required: true,
            },
            { name: 'actif', label: 'Active', type: 'checkbox' },
          ]}
        />
      )}
      {tab === 'parcours' && (
        <ResourceManager
          variant="superieur"
          resource="formations/parcours"
          headingLevel={2}
          title="Parcours"
          filters={{ formation: id }}
          fixedValues={{ formation: Number(id) }}
          columns={[{ Header: 'Code', accessor: 'code' }, { Header: 'Nom', accessor: 'nom' }]}
          fields={[
            { name: 'code', label: 'Code', required: true },
            { name: 'nom', label: 'Nom', required: true },
            { name: 'specialisation', label: 'Spécialisation' },
          ]}
        />
      )}
      {tab === 'structure' && (
        <Box sx={{ display: 'grid', gap: 4 }}>
          {maquette && (
            <Stack direction="row" spacing={2} useFlexGap sx={{ flexWrap: 'wrap' }}>
              <Button onClick={() => { setMaquette(null); setUE(null); }}>Toutes les maquettes</Button>
              {ue && <Button onClick={() => setUE(null)}>Retour aux UE — {maquette.annee_libelle}</Button>}
            </Stack>
          )}
          {!maquette && (
          <ResourceManager
            variant="superieur"
            resource="formations/maquettes"
            headingLevel={2}
            title="Maquettes annuelles"
            searchable={false}
            filters={{ formation: id }}
            fixedValues={{ formation: Number(id) }}
            onSelect={value => { setMaquette(value); setUE(null); }}
            columns={[{ Header: 'Année', accessor: 'annee_libelle' }, { Header: 'Statut', accessor: 'statut' }]}
            fields={[{
              name: 'annee_universitaire',
              label: 'Année universitaire',
              resource: 'etablissement/annees',
              labelField: 'libelle',
              required: true,
              createOnly: true,
            }]}
          />
          )}
          {!maquette && <Alert severity="info">Sélectionnez une maquette pour gérer ses unités d’enseignement.</Alert>}
          {maquette && !ue && (
            <ResourceManager
              key={`ue-${maquette.id}`}
              variant="superieur"
              resource="ue-ecue/ues"
              headingLevel={2}
              title={`UE — ${maquette.annee_libelle}`}
              filters={{ maquette: maquette.id }}
              fixedValues={{ maquette: maquette.id }}
              onSelect={setUE}
              columns={[
                { Header: 'Code', accessor: 'code' }, { Header: 'Nom', accessor: 'nom' },
                { Header: 'Semestre', accessor: 'semestre_libelle' }, { Header: 'Crédits', accessor: 'credits_ects' },
              ]}
              fields={[
                { name: 'code', label: 'Code', required: true },
                { name: 'nom', label: 'Nom', required: true },
                {
                  name: 'semestre',
                  label: 'Semestre',
                  resource: 'etablissement/semestres',
                  labelField: 'libelle',
                  filters: { annee_universitaire: maquette.annee_universitaire },
                  required: true,
                },
                {
                  name: 'credits_ects', label: 'Crédits', type: 'number', required: true, defaultValue: 0,
                },
              ]}
            />
          )}
          {ue && (
            <ResourceManager
              key={`ecue-${ue.id}`}
              variant="superieur"
              resource="ue-ecue/ecues"
              headingLevel={2}
              title={`ECUE — ${ue.nom}`}
              filters={{ ue: ue.id }}
              fixedValues={{ ue: ue.id }}
              columns={[
                { Header: 'Code', accessor: 'code' }, { Header: 'Nom', accessor: 'nom' },
                { Header: 'Crédits', accessor: 'credits_ects' }, { Header: 'Coefficient', accessor: 'coefficient' },
              ]}
              fields={[
                { name: 'code', label: 'Code', required: true },
                { name: 'nom', label: 'Nom', required: true },
                {
                  name: 'credits_ects', label: 'Crédits', type: 'number', required: true, defaultValue: 0,
                },
                {
                  name: 'coefficient', label: 'Coefficient', type: 'number', required: true, defaultValue: 1,
                },
                { name: 'programme', label: 'Programme', multiline: true },
              ]}
            />
          )}
        </Box>
      )}
      {tab === 'etudiants' && (
        <ResourceManager
          variant="superieur"
          resource="inscriptions"
          headingLevel={2}
          title="Étudiants inscrits"
          searchable={false}
          filters={{ formation: id }}
          columns={[
            { Header: 'Étudiant', accessor: 'etudiant_nom' }, { Header: 'Année', accessor: 'annee_universitaire_libelle' },
            { Header: 'Statut', accessor: 'statut_display' },
          ]}
        />
      )}
      {tab === 'emploi' && (
        <ResourceManager
          variant="superieur"
          resource="edt/creneaux-cours"
          headingLevel={2}
          title="Créneaux de la formation"
          filters={{ formation: id }}
          columns={[
            { Header: 'Jour', accessor: 'jour_display' }, { Header: 'Horaire', accessor: 'horaire' },
            { Header: 'ECUE', accessor: 'ecue_nom' }, { Header: 'Salle', accessor: 'salle_code' },
            { Header: 'Enseignant', accessor: 'enseignant_nom' },
          ]}
        />
      )}
      {tab === 'historique' && <WorkflowHistoryPanel apiType="superieur" endpoint={`formations/formations/${id}/historique/`} title="Historique de la formation" />}
    </Box>
  );
};

export default FormationDetailPage;
