import React from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import {
  Alert, Box, Button, Card, CardContent, CardHeader, Chip, CircularProgress, Stack, Typography,
} from '@mui/material';
import { useMarkAllWorkflowNotificationsRead, useWorkflowNotifications } from '../../services/api';
import { apiErrorMessage } from '../../services/resources';
import StatusBadge, { statusPresentation } from './StatusBadge';

const channelLabels = {
  in_app: 'Centre',
  email: 'Email',
  sms: 'SMS',
  webhook: 'Webhook',
};

const WorkflowNotificationsPanel = ({ apiType = 'superieur', title = 'Notifications workflow', onlyUnread = true }) => {
  const {
    data: notifications = [], isLoading, error, refetch,
  } = useWorkflowNotifications(apiType, onlyUnread);
  const markAllRead = useMarkAllWorkflowNotificationsRead(apiType);

  return (
    <Card sx={{ mb: 3 }}>
      <CardHeader
        title={<Typography component="h2" variant="h3" className="sis-card-title">{title}</Typography>}
        action={!isLoading && !error
          ? <Chip size="small" color={notifications.length ? 'warning' : 'default'} label={notifications.length} /> : null}
      />
      <CardContent>
        {markAllRead.error && <Alert severity="error">{apiErrorMessage(markAllRead.error)}</Alert>}
        {error ? (
          <Alert severity="error">
            Impossible de charger les notifications. {apiErrorMessage(error)}
            <Button variant="text" onClick={() => refetch()}>Réessayer</Button>
          </Alert>
        ) : null}
        {!error && isLoading && (
          <Box sx={{ textAlign: 'center', py: 2 }}><CircularProgress size={24} aria-label="Chargement des notifications" /></Box>
        )}
        {!error && !isLoading && notifications.length === 0 && (
          <Typography color="text.secondary">{onlyUnread ? 'Aucune notification workflow non lue.' : 'Aucune notification workflow récente.'}</Typography>
        )}
        {!error && !isLoading && notifications.length > 0 && (
          <>
            <Box sx={{ mb: 2 }}>
              {notifications.slice(0, onlyUnread ? 5 : 10).map((notification) => {
                const delivery = notification.metadata?.delivery || {};
                return (
                  <Box key={notification.id} className="sis-notification">
                    <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                      <Typography component="strong" fontWeight={700}>{notification.title}</Typography>
                      <Chip size="small" color="info" label={notification.category} />
                    </Stack>
                    <Typography variant="body2" color="text.secondary">{notification.message}</Typography>
                    {notification.event?.app_label === 'core' && notification.event?.model === 'reclamation' && (
                      <Link to={`/${apiType}/reclamations?dossier=${encodeURIComponent(notification.event.object_id)}`}>
                        Consulter la réclamation
                      </Link>
                    )}
                    {notification.event?.app_label === 'core' && notification.event?.model === 'accessdelegation' && (
                      <Link to={`/${apiType}/missions`}>Consulter mes missions</Link>
                    )}
                    {notification.event?.app_label === 'core' && ['signatureapproval', 'signaturemandate'].includes(notification.event?.model) && (
                      <Link to={`/${apiType}/signatures`}>Consulter les signatures</Link>
                    )}
                    {notification.event?.app_label === 'core' && notification.event?.model === 'documentarchive' && (
                      <Link to={`/${apiType}/archives`}>Consulter les documents archivés</Link>
                    )}
                    {Object.keys(delivery).length > 0 && (
                    <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, flexWrap: 'wrap' }}>
                      {Object.entries(delivery).map(([channel, state]) => (
                        <StatusBadge
                          key={`${notification.id}-${channel}`}
                          value={state?.status}
                          label={`${channelLabels[channel] || channel}: ${statusPresentation(state?.status).label}`}
                        />
                      ))}
                    </Stack>
                    )}
                    {Object.entries(delivery).some(([, state]) => state?.last_error) && (
                    <Typography variant="body2" color="error.main" sx={{ mt: 1 }}>
                      {Object.entries(delivery)
                        .filter(([, state]) => state?.last_error)
                        .map(([channel, state]) => `${channelLabels[channel] || channel}: ${state.last_error}`)
                        .join(' • ')}
                    </Typography>
                    )}
                    <Typography variant="body2" color="text.secondary">{notification.event?.created_at || notification.created_at}</Typography>
                  </Box>
                );
              })}
            </Box>
            {onlyUnread && (
              <Button
                size="small"
                variant="outlined"
                onClick={() => markAllRead.mutate()}
                disabled={markAllRead.isPending}
              >
                Tout marquer comme lu
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

WorkflowNotificationsPanel.propTypes = {
  apiType: PropTypes.oneOf(['secondaire', 'superieur']),
  title: PropTypes.string,
  onlyUnread: PropTypes.bool,
};
WorkflowNotificationsPanel.defaultProps = {
  apiType: 'superieur', title: 'Notifications workflow', onlyUnread: true,
};

export default WorkflowNotificationsPanel;
