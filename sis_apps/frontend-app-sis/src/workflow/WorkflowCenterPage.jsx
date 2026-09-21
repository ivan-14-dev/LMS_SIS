import React, { useMemo, useState } from 'react';
import { Row, Col, Card, Form } from '@openedx/paragon';
import {
  Box, Card as MuiCard, CardContent, Chip, LinearProgress, Stack, Typography,
} from '@mui/material';
import {
  PageHeader, SISDataTable, StatCard, WorkflowNotificationsPanel,
} from '../components/common';
import {
  useWorkflowEvents,
  useWorkflowNotifications,
  useWorkflowNotificationSummary,
  useWorkflowNotificationTrends,
} from '../services/api';

const channelLabels = {
  in_app: 'Centre',
  email: 'Email',
  sms: 'SMS',
  webhook: 'Webhook',
};

const statusLabels = {
  sent: 'Livré',
  queued: 'En file',
  retrying: 'Reprise',
  failed: 'Échec',
  skipped: 'Ignoré',
  pending: 'En attente',
};

const statusColor = {
  sent: 'success',
  queued: 'info',
  retrying: 'warning',
  failed: 'error',
  skipped: 'default',
  pending: 'primary',
};

const SummaryBarCard = ({
  title, items, total, formatLabel,
}) => (
  <MuiCard sx={{ height: '100%' }}>
    <CardContent>
      <Typography variant="h6" gutterBottom>{title}</Typography>
      {items.length === 0 ? (
        <Typography variant="body2" color="text.secondary">Aucune donnée disponible.</Typography>
      ) : (
        <Stack spacing={2}>
          {items.map(({ key, value }) => {
            const ratio = total > 0 ? (value / total) * 100 : 0;
            return (
              <Box key={key}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mb: 0.75 }}>
                  <Typography variant="body2">{formatLabel(key)}</Typography>
                  <Typography variant="body2" color="text.secondary">{value}</Typography>
                </Box>
                <LinearProgress variant="determinate" value={ratio} sx={{ height: 8, borderRadius: 999 }} />
              </Box>
            );
          })}
        </Stack>
      )}
    </CardContent>
  </MuiCard>
);

const SummaryChipCard = ({
  title, items, formatLabel, chipColor,
}) => (
  <MuiCard sx={{ height: '100%' }}>
    <CardContent>
      <Typography variant="h6" gutterBottom>{title}</Typography>
      {items.length === 0 ? (
        <Typography variant="body2" color="text.secondary">Aucune donnée disponible.</Typography>
      ) : (
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
          {items.map(({ key, value }) => (
            <Chip key={key} label={`${formatLabel(key)} • ${value}`} size="small" color={chipColor ? chipColor(key) : 'default'} />
          ))}
        </Stack>
      )}
    </CardContent>
  </MuiCard>
);

const TrendBarsCard = ({
  title, rows, total, formatValue,
}) => (
  <MuiCard sx={{ height: '100%' }}>
    <CardContent>
      <Typography variant="h6" gutterBottom>{title}</Typography>
      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">Aucune tendance disponible.</Typography>
      ) : (
        <Stack spacing={1.5}>
          {rows.map((row) => {
            const value = formatValue(row);
            const ratio = total > 0 ? (value / total) * 100 : 0;
            return (
              <Box key={row.period}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mb: 0.75 }}>
                  <Typography variant="body2">{row.period}</Typography>
                  <Typography variant="body2" color="text.secondary">{value}</Typography>
                </Box>
                <LinearProgress variant="determinate" value={ratio} sx={{ height: 8, borderRadius: 999 }} />
              </Box>
            );
          })}
        </Stack>
      )}
    </CardContent>
  </MuiCard>
);

const WorkflowCenterPage = ({ apiType = 'superieur', title, subtitle }) => {
  const [action, setAction] = useState('');
  const [appLabel, setAppLabel] = useState('');
  const [model, setModel] = useState('');
  const [notificationCategory, setNotificationCategory] = useState('');
  const [deliveryChannel, setDeliveryChannel] = useState('');
  const [deliveryStatus, setDeliveryStatus] = useState('');
  const [trendGranularity, setTrendGranularity] = useState('day');
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
  const { data: notificationSummary = {} } = useWorkflowNotificationSummary(apiType, notificationParams);
  const { data: notificationTrends = {} } = useWorkflowNotificationTrends(apiType, notificationParams);

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
  const sentCount = notificationSummary.by_status?.sent || 0;
  const failedCount = notificationSummary.by_status?.failed || 0;
  const retryingCount = notificationSummary.by_status?.retrying || 0;
  const notificationTotal = notificationSummary.total_notifications || notificationRows.length;
  const channelSummaryText = useMemo(
    () => Object.entries(notificationSummary.by_channel || {})
      .map(([channel, count]) => `${channel}: ${count}`)
      .join(' • '),
    [notificationSummary],
  );
  const statusSummaryItems = useMemo(
    () => Object.entries(notificationSummary.by_status || {})
      .map(([key, value]) => ({ key, value }))
      .sort((a, b) => b.value - a.value),
    [notificationSummary],
  );
  const channelSummaryItems = useMemo(
    () => Object.entries(notificationSummary.by_channel || {})
      .map(([key, value]) => ({ key, value }))
      .sort((a, b) => b.value - a.value),
    [notificationSummary],
  );
  const categorySummaryItems = useMemo(
    () => Object.entries(notificationSummary.by_category || {})
      .map(([key, value]) => ({ key, value }))
      .sort((a, b) => b.value - a.value),
    [notificationSummary],
  );
  const channelStatusSummaryItems = useMemo(
    () => Object.entries(notificationSummary.by_channel_status || {})
      .map(([key, value]) => ({ key, value }))
      .sort((a, b) => b.value - a.value),
    [notificationSummary],
  );
  const trendRows = useMemo(
    () => (notificationTrends?.[trendGranularity] || []).slice(-8),
    [notificationTrends, trendGranularity],
  );
  const trendTotalMax = useMemo(
    () => Math.max(0, ...trendRows.map((row) => row.total_notifications || 0)),
    [trendRows],
  );
  const trendSentMax = useMemo(
    () => Math.max(0, ...trendRows.map((row) => row.sent || 0)),
    [trendRows],
  );
  const trendFailedMax = useMemo(
    () => Math.max(0, ...trendRows.map((row) => row.failed || 0)),
    [trendRows],
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
      <Row className="mb-4">
        <Col md={6}>
          <StatCard title="Notifications suivies" value={notificationTotal} variant="info" />
        </Col>
        <Col md={6}>
          <Card>
            <Card.Body>
              <strong>Répartition par canal</strong>
              <div className="small text-muted mt-2">
                {channelSummaryText || 'Aucune livraison enregistrée.'}
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <Row className="mb-4">
        <Col lg={6} className="mb-3">
          <SummaryBarCard
            title="Répartition par statut"
            items={statusSummaryItems}
            total={Object.values(notificationSummary.by_status || {}).reduce((sum, value) => sum + value, 0)}
            formatLabel={(key) => statusLabels[key] || key}
          />
        </Col>
        <Col lg={6} className="mb-3">
          <SummaryBarCard
            title="Répartition par canal"
            items={channelSummaryItems}
            total={Object.values(notificationSummary.by_channel || {}).reduce((sum, value) => sum + value, 0)}
            formatLabel={(key) => channelLabels[key] || key}
          />
        </Col>
      </Row>
      <Row className="mb-4">
        <Col lg={6} className="mb-3">
          <SummaryChipCard
            title="Catégories de notifications"
            items={categorySummaryItems}
            formatLabel={(key) => key}
          />
        </Col>
        <Col lg={6} className="mb-3">
          <SummaryChipCard
            title="Détail canal / statut"
            items={channelStatusSummaryItems}
            formatLabel={(key) => {
              const [channel, status] = key.split(':');
              return `${channelLabels[channel] || channel} / ${statusLabels[status] || status}`;
            }}
            chipColor={(key) => {
              const [, status] = key.split(':');
              return statusColor[status] || 'default';
            }}
          />
        </Col>
      </Row>
      <MuiCard sx={{ mb: 4 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, alignItems: 'center', mb: 3, flexWrap: 'wrap' }}>
            <Typography variant="h6">Tendances temporelles des livraisons</Typography>
            <Form.Group className="mb-0">
              <Form.Label>Granularité</Form.Label>
              <Form.Control as="select" value={trendGranularity} onChange={(e) => setTrendGranularity(e.target.value)}>
                <option value="day">Jour</option>
                <option value="week">Semaine</option>
                <option value="month">Mois</option>
              </Form.Control>
            </Form.Group>
          </Box>
          <Row>
            <Col lg={4} className="mb-3">
              <TrendBarsCard
                title="Notifications suivies"
                rows={trendRows}
                total={trendTotalMax}
                formatValue={(row) => row.total_notifications || 0}
              />
            </Col>
            <Col lg={4} className="mb-3">
              <TrendBarsCard
                title="Livraisons réussies"
                rows={trendRows}
                total={trendSentMax}
                formatValue={(row) => row.sent || 0}
              />
            </Col>
            <Col lg={4} className="mb-3">
              <TrendBarsCard
                title="Livraisons en échec"
                rows={trendRows}
                total={trendFailedMax}
                formatValue={(row) => row.failed || 0}
              />
            </Col>
          </Row>
        </CardContent>
      </MuiCard>
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
