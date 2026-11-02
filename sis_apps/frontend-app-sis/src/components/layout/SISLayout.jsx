import React from 'react';
import PropTypes from 'prop-types';
import { Navigate, Outlet } from 'react-router-dom';
import { getEnabledVariants } from '../../services/resources';
import Sidebar from './Sidebar';
import LocalSessionGate from '../auth/LocalSessionGate';

const SISLayout = ({ type }) => (type !== 'admin' && !getEnabledVariants().includes(type) ? (
  <Navigate to={`/${getEnabledVariants()[0]}`} replace />
) : (
  <LocalSessionGate variant={type}>
    <div className="sis-layout">
      <Sidebar type={type} />
      <div className="sis-content">
        <Outlet />
      </div>
    </div>
  </LocalSessionGate>
));

SISLayout.propTypes = {
  type: PropTypes.oneOf(['superieur', 'secondaire', 'admin']).isRequired,
};

export default SISLayout;
