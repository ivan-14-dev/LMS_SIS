import React from 'react';
import PropTypes from 'prop-types';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

const SISLayout = ({ type }) => (
  <div className="sis-layout">
    <Sidebar type={type} />
    <div className="sis-content">
      <Outlet />
    </div>
  </div>
);

SISLayout.propTypes = {
  type: PropTypes.oneOf(['superieur', 'secondaire', 'admin']).isRequired,
};

export default SISLayout;
