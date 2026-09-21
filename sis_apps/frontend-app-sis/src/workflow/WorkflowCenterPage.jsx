import React, { useMemo, useState } from 'react';
import { Row, Col, Card, Form } from '@openedx/paragon';
import {
  PageHeader, SISDataTable, StatCard, WorkflowNotificationsPanel,
} from '../components/common';
import { useWorkflowEvents } from '../services/api';

const WorkflowCenterPage = ({ apiType = 'superieur', title, subtitle }) => {
  const [action, setAction] = useState('');
  const [appLabel, setAppLabel] = useState('');
  const [model, setModel] = useState('');
  const params = useMemo(() => ({
    ...(action ? { action } : {}),
    ...(appLabel ? { app_label: appLabel } : {}),
    ...(model ? { model } : {}),
  }), [action, appLabel, model]);
  const { data: events = [], isLoading } = useWorkflowEvents(apiType, params);

  const actionOptions = useMemo(
    () => [...new Set(events.map((event) => event.action).filter(Boolean))].sort(),
    [events],
  );
  const moduleOptions = useMemo(
    () => [...new Set(events.map((event) => event.app_label).filter(Boolean))].sort(),
    [events],
  );
  const modelOptions = useMemo(
    () => [...new Set(events.map((event) => event.model).filter(Boolean))].sort(),
    [events],
  );

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
      <Card className="mb-4">
        <Card.Header><Card.Title className="mb-0">Filtres</Card.Title></Card.Header>
        <Card.Body>
          <Row>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Action</Form.Label>
                <Form.Control as="select" value={action} onChange={(e) => setAction(e.target.value)}>
                  <option value="">Toutes</option>
                  {actionOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </Form.Control>
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Module</Form.Label>
                <Form.Control as="select" value={appLabel} onChange={(e) => setAppLabel(e.target.value)}>
                  <option value="">Tous</option>
                  {moduleOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </Form.Control>
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Modèle</Form.Label>
                <Form.Control as="select" value={model} onChange={(e) => setModel(e.target.value)}>
                  <option value="">Tous</option>
                  {modelOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </Form.Control>
              </Form.Group>
            </Col>
          </Row>
        </Card.Body>
      </Card>
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
