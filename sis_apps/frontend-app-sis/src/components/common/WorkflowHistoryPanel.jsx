import React from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Badge, Card, Spinner,
} from '@openedx/paragon';
import { useWorkflowHistory } from '../../services/api';
import { apiErrorMessage } from '../../services/resources';

const WorkflowHistoryPanel = ({
  apiType = 'superieur',
  endpoint,
  title = 'Historique workflow',
  emptyMessage = 'Aucun événement workflow disponible.',
}) => {
  const { data: events = [], isLoading, error } = useWorkflowHistory(apiType, endpoint, Boolean(endpoint));
  const renderHistory = () => {
    if (!endpoint) {
      return <p className="text-muted mb-0">Sélectionnez un élément pour consulter son historique.</p>;
    }
    if (isLoading) {
      return <div className="text-center py-3"><Spinner animation="border" size="sm" /></div>;
    }
    if (error) {
      return <Alert variant="danger">{apiErrorMessage(error)}</Alert>;
    }
    if (!events.length) {
      return <p className="text-muted mb-0">{emptyMessage}</p>;
    }
    return events.map(event => (
      <div key={event.id} className="sis-panel mb-2">
        <div className="d-flex flex-wrap align-items-center justify-content-between">
          <strong>{event.title}</strong>
          <Badge variant="light">{event.action}</Badge>
        </div>
        <div className="small">{event.message || event.object_repr}</div>
        <div className="small text-muted">
          {event.actor_nom || 'Système'}{' · '}{event.created_at}
        </div>
      </div>
    ));
  };

  return (
    <Card className="mt-4">
      <Card.Header title={<h2 className="sis-card-title">{title}</h2>} />
      <Card.Body>
        {renderHistory()}
      </Card.Body>
    </Card>
  );
};

WorkflowHistoryPanel.propTypes = {
  apiType: PropTypes.oneOf(['secondaire', 'superieur']),
  endpoint: PropTypes.string,
  title: PropTypes.string,
  emptyMessage: PropTypes.string,
};

WorkflowHistoryPanel.defaultProps = {
  apiType: 'superieur',
  endpoint: '',
  title: 'Historique workflow',
  emptyMessage: 'Aucun événement workflow disponible.',
};

export default WorkflowHistoryPanel;
