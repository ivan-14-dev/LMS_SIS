import React from 'react';
import { useParams } from 'react-router-dom';
import { Row, Col, Card, Button, Tabs, Tab, Spinner } from '@openedx/paragon';
import { Edit } from '@openedx/paragon/icons';
import { PageHeader, WorkflowHistoryPanel, WorkflowNotificationsPanel } from '../../components/common';
import { useFormation } from '../../services/api';

const FormationDetailPage = () => {
  const { id } = useParams();
  const { data: formation, isLoading } = useFormation(id);

  if (isLoading) {
    return <div className="text-center py-5"><Spinner animation="border" /></div>;
  }

  if (!formation) {
    return <div>Formation non trouvée</div>;
  }

  return (
    <div>
      <PageHeader
        title={formation.nom}
        subtitle={`Code: ${formation.code}`}
        showBack
        breadcrumbs={[
          { label: 'Formations', path: '/superieur/formations' },
          { label: formation.nom },
        ]}
        actions={
          <Button variant="primary" iconBefore={Edit}>Modifier</Button>
        }
      />
      <WorkflowNotificationsPanel apiType="superieur" />

      <Row>
        <Col md={4}>
          <Card className="mb-4">
            <Card.Header><Card.Title>Informations</Card.Title></Card.Header>
            <Card.Body>
              <dl>
                <dt>Département</dt>
                <dd>{formation.departement_nom}</dd>
                <dt>Niveau</dt>
                <dd>{formation.niveau_display}</dd>
                <dt>Durée</dt>
                <dd>{formation.nb_semestres} semestres</dd>
                <dt>Crédits ECTS</dt>
                <dd>{formation.credits_total}</dd>
                <dt>Responsable</dt>
                <dd>{formation.responsable_nom || 'Non assigné'}</dd>
                <dt>Statut</dt>
                <dd>{formation.actif ? 'Active' : 'Inactive'}</dd>
              </dl>
            </Card.Body>
          </Card>
          <WorkflowHistoryPanel
            apiType="superieur"
            endpoint={`formations/formations/${id}/historique/`}
            title="Historique workflow"
          />
        </Col>
        <Col md={8}>
          <Card>
            <Card.Body>
              <Tabs defaultActiveKey="ues">
                <Tab eventKey="ues" title="UEs/ECUEs">
                  <div className="pt-3">
                    <p className="text-muted">Structure de la formation (UEs et ECUEs)...</p>
                  </div>
                </Tab>
                <Tab eventKey="etudiants" title="Étudiants">
                  <div className="pt-3">
                    <p className="text-muted">Liste des étudiants inscrits...</p>
                  </div>
                </Tab>
                <Tab eventKey="emploi" title="Emploi du temps">
                  <div className="pt-3">
                    <p className="text-muted">Emploi du temps de la formation...</p>
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

export default FormationDetailPage;
