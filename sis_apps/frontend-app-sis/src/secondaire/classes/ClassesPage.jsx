import React, { useState } from 'react';
import {
  Alert, Box, Button, Tab, Tabs,
} from '@mui/material';
import ResourceManager from '../../components/common/ResourceManager';
import { PageHeader, WorkflowHistoryPanel } from '../../components/common';
import RecordsTabs from '../../components/common/RecordsTabs';
import admissionActions from '../../components/common/admissionActions';

const ClassesPage = () => {
  const [selected, setSelected] = useState(null);
  const [enrollment, setEnrollment] = useState(null);
  const [tab, setTab] = useState(0);
  return (
    <>
      <Tabs value={tab} onChange={(_, value) => { setTab(value); setSelected(null); setEnrollment(null); }} aria-label="Gestion des classes" sx={{ mb: 3 }}>
        <Tab label="Classes" />
        <Tab label="Inscriptions annuelles" />
      </Tabs>
      {tab === 0 && !selected && (
      <ResourceManager
        variant="secondaire"
        resource="classes/classes"
        title="Classes"
        onSelect={setSelected}
        columns={[
          { Header: 'Classe', accessor: 'nom' },
          { Header: 'Offre', accessor: 'offre_code' },
          { Header: 'Origine des règles', accessor: 'configuration_origine.source.label' },
          { Header: 'Niveau', accessor: 'niveau_nom' },
          { Header: 'Année', accessor: 'annee_libelle' },
          { Header: 'Effectif', accessor: 'effectif' },
          { Header: 'Capacité', accessor: 'effectif_max' },
        ]}
        fields={[
          { name: 'nom', label: 'Nom de la classe', required: true },
          {
            name: 'organisation_unit',
            label: 'Unité d’organisation',
            resource: 'etablissement/unites',
            createOnly: true,
            labelField: 'label',
          },
          {
            name: 'offre_code',
            label: 'Offre institutionnelle',
            helpText: 'À la création, laissez vide pour hériter des règles de l’unité ou de l’établissement.',
            resource: 'etablissement/learning-offerings',
            valueField: 'code',
            labelField: 'label',
          },
          {
            name: 'niveau', label: 'Niveau', resource: 'etablissement/niveaux', labelField: 'libelle', required: true,
          },
          {
            name: 'annee_scolaire',
            label: 'Année scolaire',
            resource: 'etablissement/annees',
            labelField: 'libelle',
            required: true,
          },
          {
            name: 'effectif_max', label: 'Capacité maximale', type: 'number', defaultValue: 40, required: true,
          },
          {
            name: 'prof_principal', label: 'Professeur principal', resource: 'utilisateurs/comptes', labelField: 'full_name',
          },
          { name: 'salle_principale', label: 'Salle principale', resource: 'salles' },
        ]}
      />
      )}
      {tab === 1 && (
      <Box>
        <Alert severity="info" sx={{ mb: 3 }}>
          Une réinscription ouvre une nouvelle demande pour l’année suivante,
          sans modifier les bulletins ou règles antérieurs.
          La validation d’une année future ne remplace pas immédiatement la classe actuelle.
          Suspension et abandon libèrent la place sans effacer les résultats.
          La reprise exige une place disponible et une année en cours non clôturée.
          Après un abandon ou la fin de l’année, utilisez une réinscription.
        </Alert>
        <ResourceManager
          variant="secondaire"
          resource="eleves/inscriptions"
          title="Inscriptions annuelles"
          onSelect={setEnrollment}
          searchable={false}
          columns={[
            { Header: 'Élève', accessor: 'eleve_nom' },
            { Header: 'Classe', accessor: 'classe_nom' },
            { Header: 'Année', accessor: 'annee_libelle' },
            { Header: 'Offre', accessor: 'offre_configuration.label' },
            { Header: 'Statut', accessor: 'statut_display' },
          ]}
          fields={[
            {
              name: 'eleve', label: 'Élève', resource: 'eleves', labelField: 'full_name', required: true, createOnly: true,
            },
            {
              name: 'classe', label: 'Classe', resource: 'classes/classes', required: true, createOnly: true,
            },
            {
              name: 'annee_scolaire',
              label: 'Année scolaire',
              resource: 'etablissement/annees',
              labelField: 'libelle',
              required: true,
              createOnly: true,
            },
            {
              name: 'date_inscription', label: 'Date d’inscription', type: 'date', required: true,
            },
          ]}
          actions={admissionActions('secondaire')}
        />
        {enrollment && (
        <WorkflowHistoryPanel
          apiType="secondaire"
          endpoint={`eleves/inscriptions/${enrollment.id}/historique/`}
          title="Historique de l’admission"
        />
        )}
      </Box>
      )}
      {tab === 0 && selected && (
        <Box sx={{ mt: 3 }}>
          <Button onClick={() => setSelected(null)}>Retour aux classes</Button>
          <PageHeader title={`Classe : ${selected.nom}`} />
          <RecordsTabs
            label="Détails de la classe"
            panels={[
              {
                label: 'Élèves',
                content: (
                  <ResourceManager
                    key={selected.id}
                    variant="secondaire"
                    resource="eleves"
                    headingLevel={2}
                    filters={{ classe_actuelle: selected.id }}
                    title={`Élèves — ${selected.nom}`}
                    searchable={false}
                    columns={[
                      { Header: 'Matricule', accessor: 'matricule' },
                      { Header: 'Nom', accessor: 'full_name' },
                    ]}
                    actions={[{
                      label: 'Changer de classe',
                      endpoint: 'changer-classe',
                      fields: [
                        {
                          name: 'classe_id',
                          label: 'Classe de destination',
                          resource: 'classes/classes',
                          required: true,
                          filters: { annee_scolaire: selected.annee_scolaire },
                        },
                        {
                          name: 'motif', label: 'Motif du transfert', required: true, multiline: true,
                        },
                      ],
                    }]}
                  />
                ),
              },
              {
                label: 'Historique',
                content: (
                  <WorkflowHistoryPanel
                    apiType="secondaire"
                    endpoint={`classes/classes/${selected.id}/historique/`}
                    title="Historique de la classe"
                  />
                ),
              },
            ]}
          />
        </Box>
      )}
    </>
  );
};

export default ClassesPage;
