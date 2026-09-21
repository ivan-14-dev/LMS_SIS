import React from 'react';
import { Row, Col } from '@openedx/paragon';
import {
  PageHeader, SISDataTable, StatCard, WorkflowNotificationsPanel,
} from '../components/common';
import { useWorkflowEvents } from '../services/api';

const WorkflowCenterPage = ({ apiType = 'superieur', title, subtitle }) => {
  const { data: events = [], isLoading } = useWorkflowEvents(apiType);

  const columns = [
    { Header: 'Action', accessor: 'action' },
    { Header: 'Titre', accessor: 'title' },
    { Header: 'Module', accessor: 'app_label' },
    { Header: 'Modèle', accessor: 'model' },
    { Header: 'Objet', accessor: 'object_repr' },
    { Header: 'Acteur', accessor: 'actor_nom' },
    { Header: 'Date', accessor: 'created_at' },
  ];

  return (
    <div>
      <PageHeader
        title={title}
        subtitle={subtitle}
      />
      <WorkflowNotificationsPanel apiType={apiType} title="Notifications workflow récentes" />
      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Événements" value={events.length} variant="primary" />
        </Col>
        <Col md={4}>
          <StatCard title="Publications/signatures" value={events.filter((event) => ['publication', 'signature'].includes(event.action)).length} variant="success" />
        </Col>
        <Col md={4}>
          <StatCard title="Créations/mises à jour" value={events.filter((event) => ['creation', 'mise_a_jour'].includes(event.action)).length} variant="info" />
        </Col>
      </Row>
      <SISDataTable
        title="Historique global des workflows"
        data={events}
        columns={columns}
        loading={isLoading}
        searchable
        exportable
      />
    </div>
  );
};

export default WorkflowCenterPage;
