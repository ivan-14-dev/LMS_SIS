import React from 'react';
import PropTypes from 'prop-types';
import { Card, Spinner } from '@openedx/paragon';

const StatCard = ({
  title, value, icon, variant, loading, trend, trendValue,
}) => (
  <Card className="sis-stat-card">
    <Card.Body>
      <div className="d-flex justify-content-between align-items-start">
        <div>
          {loading ? (
            <Spinner animation="border" size="sm" />
          ) : (
            <div className="sis-stat-card__value">{value}</div>
          )}
          <div className="sis-stat-card__label">{title}</div>
          {trend && (
            <small className={`text-${trend === 'up' ? 'success' : 'danger'}`}>
              {trend === 'up' ? '↑' : '↓'} {trendValue}
            </small>
          )}
        </div>
        <div className={`sis-stat-card__icon sis-stat-card__icon--${variant}`}>
          {icon}
        </div>
      </div>
    </Card.Body>
  </Card>
);

StatCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  icon: PropTypes.node.isRequired,
  variant: PropTypes.oneOf(['primary', 'success', 'warning', 'danger']),
  loading: PropTypes.bool,
  trend: PropTypes.oneOf(['up', 'down']),
  trendValue: PropTypes.string,
};

StatCard.defaultProps = {
  variant: 'primary',
  loading: false,
  trend: null,
  trendValue: '',
};

export default StatCard;
