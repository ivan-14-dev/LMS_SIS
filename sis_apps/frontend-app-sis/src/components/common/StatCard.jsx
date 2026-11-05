import React from 'react';
import PropTypes from 'prop-types';
import {
  Box, Card, CardContent, CircularProgress, Stack, Typography,
} from '@mui/material';

const StatCard = ({
  title, value, icon, variant, loading, trend, trendValue,
}) => (
  <Card className="sis-stat-card">
    <CardContent>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
        <Box sx={{ minWidth: 0 }}>
          {loading ? (
            <CircularProgress size={24} aria-label={`Chargement : ${title}`} />
          ) : (
            <Typography component="div" className="sis-stat-card__value" sx={{ fontSize: '1.75rem', fontWeight: 700 }}>
              {value}
            </Typography>
          )}
          <Typography component="div" variant="body2" color="text.secondary" className="sis-stat-card__label">{title}</Typography>
          {trend && (
            <Typography variant="caption" color={trend === 'up' ? 'success.main' : 'error.main'}>
              {trend === 'up' ? '↑' : '↓'} {trendValue}
            </Typography>
          )}
        </Box>
        {icon && <Box className={`sis-stat-card__icon sis-stat-card__icon--${variant}`} aria-hidden="true">{icon}</Box>}
      </Stack>
    </CardContent>
  </Card>
);

StatCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  icon: PropTypes.node,
  variant: PropTypes.oneOf(['primary', 'success', 'warning', 'danger', 'info']),
  loading: PropTypes.bool,
  trend: PropTypes.oneOf(['up', 'down']),
  trendValue: PropTypes.string,
};

StatCard.defaultProps = {
  variant: 'primary',
  icon: null,
  loading: false,
  trend: null,
  trendValue: '',
};

export default StatCard;
