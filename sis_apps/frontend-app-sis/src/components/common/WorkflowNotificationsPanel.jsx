import React from 'react';
import {
  Badge, Button, Card, Spinner,
} from '@openedx/paragon';
import { useMarkAllWorkflowNotificationsRead, useWorkflowNotifications } from '../../services/api';

const statusVariant = {
  sent: 'success',
  queued: 'info',
  retrying: 'warning',
  failed: 'danger',
  skipped: 'light',
};

const channelLabels = {
  in_app: 'Centre',
  email: 'Email',
  sms: 'SMS',
  webhook: 'Webhook',
};

const WorkflowNotificationsPanel = ({ apiType = 'superieur', title = 'Notifications workflow', onlyUnread = true }) => {
  const { data: notifications = [], isLoading } = useWorkflowNotifications(apiType, onlyUnread);
  const markAllRead = useMarkAllWorkflowNotificationsRead(apiType);

  return (
    <Card className="mb-4">
      <Card.Header>
        <div className="d-flex align-items-center justify-content-between w-100">
          <Card.Title className="mb-0">{title}</Card.Title>
          <Badge variant={notifications.length ? 'warning' : 'light'}>{notifications.length}</Badge>
        </div>
      </Card.Header>
      <Card.Body>
        {isLoading ? (
          <div className="text-center py-3"><Spinner animation="border" size="sm" /></div>
        ) : notifications.length === 0 ? (
          <p className="text-muted mb-0">{onlyUnread ? 'Aucune notification workflow non lue.' : 'Aucune notification workflow récente.'}</p>
        ) : (
          <>
            <div className="mb-3">
              {notifications.slice(0, onlyUnread ? 5 : 10).map((notification) => {
                const delivery = notification.metadata?.delivery || {};
                return (
                <div key={notification.id} className="border rounded p-2 mb-2">
                  <div className="d-flex align-items-center justify-content-between">
                    <strong>{notification.title}</strong>
                    <Badge variant="info">{notification.category}</Badge>
                  </div>
                  <div className="small text-muted">{notification.message}</div>
                  {Object.keys(delivery).length > 0 && (
                    <div className="mt-2">
                      {Object.entries(delivery).map(([channel, state]) => (
                        <Badge key={`${notification.id}-${channel}`} variant={statusVariant[state?.status] || 'secondary'} className="mr-2 mb-1">
                          {channelLabels[channel] || channel}: {state?.status || 'pending'}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {Object.entries(delivery).some(([, state]) => state?.last_error) && (
                    <div className="small text-danger mt-1">
                      {Object.entries(delivery)
                        .filter(([, state]) => state?.last_error)
                        .map(([channel, state]) => `${channelLabels[channel] || channel}: ${state.last_error}`)
                        .join(' • ')}
                    </div>
                  )}
                  <div className="small text-muted">{notification.event?.created_at || notification.created_at}</div>
                </div>
                );
              })}
            </div>
            {onlyUnread && (
              <Button
                size="sm"
                variant="outline-primary"
                onClick={() => markAllRead.mutate()}
                disabled={markAllRead.isPending}
              >
                Tout marquer comme lu
              </Button>
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default WorkflowNotificationsPanel;
