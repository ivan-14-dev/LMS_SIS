import React from 'react';
import EvaluationsManager from '../../components/common/EvaluationsManager';
import WorkflowNotificationsPanel from '../../components/common/WorkflowNotificationsPanel';

const EvaluationsPage = () => (
  <div>
    <WorkflowNotificationsPanel apiType="secondaire" />
    <EvaluationsManager variant="secondaire" />
  </div>
);

export default EvaluationsPage;
