import React from 'react';
import {
  Badge, Card, Spinner,
} from '@openedx/paragon';
import { useWorkflowHistory } from '../../services/api';

const WorkflowHistoryPanel = ({
  apiType = 'superieur',
  endpoint,
  title = 'Historique workflow',
  emptyMessage = 'Aucun événement workflow disponible.',
}) => {
  const { data: events = [], isLoading } = useWorkflowHistory(apiType, endpoint, Boolean(endpoint));

  return (
    <Card className="mt-4">
      <Card.Header><Card.Title>{title}</Card.Title></Card.Header>
      <Card.Body>
        {!endpoint ? (
          <p className="text-muted mb-0">Sélectionnez un élément pour consulter son historique.</p>
        ) : isLoading ? (
          <div className="text-center py-3"><Spinner animation="border" size="sm" /></div>
        ) : events.length === 0 ? (
          <p className="text-muted mb-0">{emptyMessage}</p>
        ) : (
          events.map((event) => (
            <div key={event.id} className="border rounded p-2 mb-2">
              <div className="d-flex align-items-center justify-content-between">
                <strong>{event.title}</strong>
                <Badge variant="light">{event.action}</Badge>
              </div>
              <div className="small">{event.message || event.object_repr}</div>
              <div className="small text-muted">
                {event.actor_nom || 'Système'}
                {' · '}
                {event.created_at}
              </div>
            </div>
          ))
        )}
      </Card.Body>
    </Card>
  );
};

export default WorkflowHistoryPanel;
