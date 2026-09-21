import React from 'react';
import {
  Badge, Button, Card, Spinner,
} from '@openedx/paragon';
import { useMarkAllWorkflowNotificationsRead, useWorkflowNotifications } from '../../services/api';

const WorkflowNotificationsPanel = ({ apiType = 'superieur', title = 'Notifications workflow' }) => {
  const { data: notifications = [], isLoading } = useWorkflowNotifications(apiType, true);
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
          <p className="text-muted mb-0">Aucune notification workflow non lue.</p>
        ) : (
          <>
            <div className="mb-3">
              {notifications.slice(0, 5).map((notification) => (
                <div key={notification.id} className="border rounded p-2 mb-2">
                  <div className="d-flex align-items-center justify-content-between">
                    <strong>{notification.title}</strong>
                    <Badge variant="info">{notification.category}</Badge>
                  </div>
                  <div className="small text-muted">{notification.message}</div>
                  <div className="small text-muted">{notification.event?.created_at || notification.created_at}</div>
                </div>
              ))}
            </div>
            <Button
              size="sm"
              variant="outline-primary"
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
            >
              Tout marquer comme lu
            </Button>
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default WorkflowNotificationsPanel;
