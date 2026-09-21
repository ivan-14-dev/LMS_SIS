import React, { useMemo, useState } from 'react';
import { Row, Col, Card, Form } from '@openedx/paragon';
import {
  PageHeader, SISDataTable, StatCard, WorkflowNotificationsPanel,
} from '../components/common';
import { useWorkflowEvents, useWorkflowNotifications } from '../services/api';

const WorkflowCenterPage = ({ apiType = 'superieur', title, subtitle }) => {
  const [action, setAction] = useState('');
  const [appLabel, setAppLabel] = useState('');
  const [model, setModel] = useState('');
  const [notificationCategory, setNotificationCategory] = useState('');
  const [deliveryChannel, setDeliveryChannel] = useState('');
  const [deliveryStatus, setDeliveryStatus] = useState('');
  const params = useMemo(() => ({
    ...(action ? { action } : {}),
    ...(appLabel ? { app_label: appLabel } : {}),
    ...(model ? { model } : {}),
  }), [action, appLabel, model]);
  const { data: events = [], isLoading } = useWorkflowEvents(apiType, params);
  const notificationParams = useMemo(() => ({
    ...(notificationCategory ? { category: notificationCategory } : {}),
    ...(deliveryChannel ? { delivery_channel: deliveryChannel } : {}),
    ...(deliveryStatus ? { delivery_status: deliveryStatus } : {}),
  }), [notificationCategory, deliveryChannel, deliveryStatus]);
  const { data: notifications = [], isLoading: notificationsLoading } = useWorkflowNotifications(apiType, false, notificationParams);

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
  const notificationCategoryOptions = useMemo(
    () => [...new Set(notifications.map((notification) => notification.category).filter(Boolean))].sort(),
    [notifications],
  );
  const deliveryChannelOptions = useMemo(
    () => [...new Set(notifications.flatMap((notification) => notification.delivery_channels || []).filter(Boolean))].sort(),
    [notifications],
  );
  const deliveryStatusOptions = useMemo(
    () => [...new Set(
      notifications.flatMap((notification) => (notification.delivery_status_summary || [])
        .map((value) => value.split(':')[1])
        .filter(Boolean)),
    )].sort(),
    [notifications],
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
  const notificationColumns = [
    { Header: 'Titre', accessor: 'title' },
    { Header: 'Catégorie', accessor: 'category' },
    { Header: 'Canaux', accessor: 'delivery_channels_label' },
    { Header: 'Statuts', accessor: 'delivery_status_summary_label' },
    { Header: 'Erreurs', accessor: 'delivery_last_errors_label' },
    { Header: 'Date', accessor: 'created_at' },
  ];
  const notificationRows = useMemo(
    () => notifications.map((notification) => ({
      ...notification,
      delivery_channels_label: (notification.delivery_channels || []).join(', '),
      delivery_status_summary_label: (notification.delivery_status_summary || []).join(', '),
      delivery_last_errors_label: (notification.delivery_last_errors || []).join(' • '),
    })),
    [notifications],
  );
  const sentCount = useMemo(
    () => notificationRows.filter((notification) => (notification.delivery_status_summary || []).some((item) => item.endsWith(':sent'))).length,
    [notificationRows],
  );
  const failedCount = useMemo(
    () => notificationRows.filter((notification) => (notification.delivery_status_summary || []).some((item) => item.endsWith(':failed'))).length,
    [notificationRows],
  );
  const retryingCount = useMemo(
    () => notificationRows.filter((notification) => (notification.delivery_status_summary || []).some((item) => item.endsWith(':retrying'))).length,
    [notificationRows],
  );

  return (
    <div>
      <PageHeader
        title={title}
        subtitle={subtitle}
      />
      <WorkflowNotificationsPanel apiType={apiType} title="Notifications workflow récentes" onlyUnread={false} />
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
          <Row className="mt-3">
            <Col md={4}>
              <Form.Group>
                <Form.Label>Catégorie notification</Form.Label>
                <Form.Control as="select" value={notificationCategory} onChange={(e) => setNotificationCategory(e.target.value)}>
                  <option value="">Toutes</option>
                  {notificationCategoryOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </Form.Control>
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Canal livraison</Form.Label>
                <Form.Control as="select" value={deliveryChannel} onChange={(e) => setDeliveryChannel(e.target.value)}>
                  <option value="">Tous</option>
                  {deliveryChannelOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </Form.Control>
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Statut livraison</Form.Label>
                <Form.Control as="select" value={deliveryStatus} onChange={(e) => setDeliveryStatus(e.target.value)}>
                  <option value="">Tous</option>
                  {deliveryStatusOptions.map((option) => <option key={option} value={option}>{option}</option>)}
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
      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Notifications livrées" value={sentCount} variant="success" />
        </Col>
        <Col md={4}>
          <StatCard title="Notifications en reprise" value={retryingCount} variant="warning" />
        </Col>
        <Col md={4}>
          <StatCard title="Notifications en échec" value={failedCount} variant="danger" />
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
      <div className="mt-4">
        <SISDataTable
          title="Rapport des livraisons de notifications"
          data={notificationRows}
          columns={notificationColumns}
          loading={notificationsLoading}
          searchable
          exportable
          emptyMessage="Aucune notification ne correspond aux filtres."
        />
      </div>
    </div>
  );
};

export default WorkflowCenterPage;
