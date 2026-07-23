import React from 'react';
import { useParams } from 'react-router-dom';
import { Row, Col, Card, Badge, Tabs, Tab } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useEleveDetail, useNotesByEleve, usePresencesByEleve } from '../../services/api';

const EleveDetailPage = () => {
  const { id } = useParams();
  const { data: eleve, isLoading } = useEleveDetail(id);
  const { data: notes = [] } = useNotesByEleve(id);
  const { data: presences = [] } = usePresencesByEleve(id);

  const notesColumns = [
    { Header: 'Matière', accessor: 'matiere_nom' },
    { Header: 'Évaluation', accessor: 'evaluation_titre' },
    { Header: 'Note', accessor: 'note', Cell: ({ value }) => `${value}/20` },
    { Header: 'Date', accessor: 'date' },
  ];

  const presencesColumns = [
    { Header: 'Date', accessor: 'date' },
    { Header: 'Matière', accessor: 'matiere_nom' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => (
        <Badge variant={value === 'present' ? 'success' : value === 'absent' ? 'danger' : 'warning'}>
          {value}
        </Badge>
      ),
    },
    { Header: 'Justification', accessor: 'justification' },
  ];

  if (isLoading) return <div>Chargement...</div>;
  if (!eleve) return <div>Élève non trouvé</div>;

  return (
    <div>
      <PageHeader
        title={`${eleve.nom} ${eleve.prenom}`}
        subtitle={`Matricule: ${eleve.matricule}`}
        breadcrumbs={[
          { label: 'Élèves', href: '/secondaire/eleves' },
          { label: `${eleve.nom} ${eleve.prenom}` },
        ]}
      />

      <Row className="mb-4">
        <Col md={4}>
          <Card>
            <Card.Header><Card.Title>Informations personnelles</Card.Title></Card.Header>
            <Card.Body>
              <dl>
                <dt>Matricule</dt><dd>{eleve.matricule}</dd>
                <dt>Date de naissance</dt><dd>{eleve.date_naissance}</dd>
                <dt>Lieu de naissance</dt><dd>{eleve.lieu_naissance}</dd>
                <dt>Sexe</dt><dd>{eleve.sexe}</dd>
                <dt>Classe</dt><dd>{eleve.classe_nom}</dd>
                <dt>Statut</dt>
                <dd>
                  <Badge variant={eleve.statut === 'actif' ? 'success' : 'danger'}>
                    {eleve.statut}
                  </Badge>
                </dd>
              </dl>
            </Card.Body>
          </Card>
        </Col>
        <Col md={8}>
          <Card>
            <Card.Body>
              <Tabs defaultActiveKey="notes">
                <Tab eventKey="notes" title="Notes">
                  <div className="pt-3">
                    <SISDataTable title="" data={notes} columns={notesColumns} searchable={false} exportable />
                  </div>
                </Tab>
                <Tab eventKey="presences" title="Présences">
                  <div className="pt-3">
                    <SISDataTable title="" data={presences} columns={presencesColumns} searchable={false} exportable />
                  </div>
                </Tab>
              </Tabs>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default EleveDetailPage;
