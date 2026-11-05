import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Link, useLocation } from 'react-router-dom';
import {
  List, ListItemButton, SvgIcon, Tooltip,
} from '@mui/material';
import { SchoolOutlined, LockOutlined } from '@mui/icons-material';
import { matchesNavigation } from './navigation';

export const WorkspaceBrand = ({ branding }) => {
  const [failedLogo, setFailedLogo] = useState('');
  return (
    <>
      <div className="sis-sidebar__brand">
        {branding?.logo && failedLogo !== branding.logo
          ? <img className="sis-sidebar__logo" src={branding.logo} alt={`Logo ${branding.name}`} onError={() => setFailedLogo(branding.logo)} />
          : <span className="sis-sidebar__monogram" aria-hidden="true">S</span>}
        <span className="sis-sidebar__label"><strong>LMS SIS</strong><small>Votre espace éducatif</small></span>
      </div>
      {failedLogo && failedLogo === branding?.logo && <p className="sis-sidebar__empty" role="status">Logo indisponible.</p>}
    </>
  );
};
WorkspaceBrand.propTypes = { branding: PropTypes.shape({ name: PropTypes.string, logo: PropTypes.string }) };
WorkspaceBrand.defaultProps = { branding: undefined };

const Sidebar = ({
  sections, collapsed, onNavigate, branding, showBrand, institution, workspaceLabel,
}) => {
  const location = useLocation();
  return (
    <div className={`sis-sidebar${collapsed ? ' sis-sidebar--collapsed' : ''}`}>
      {showBrand && <WorkspaceBrand branding={branding} />}
      {institution && (
        <div className="sis-sidebar__workspace">
          <span className="sis-sidebar__workspace-icon"><SchoolOutlined /></span>
          <span className="sis-sidebar__label">
            <strong>{institution}</strong>
            <small><LockOutlined />{workspaceLabel}</small>
          </span>
        </div>
      )}
      <nav aria-label="Navigation principale" className="sis-sidebar__nav">
        {sections.map(section => (
          <List component="div" disablePadding key={section.title} className="sis-sidebar__section">
            <div className="sis-sidebar__section-title sis-sidebar__label">{section.title}</div>
            {section.items.map(item => (
              <Tooltip key={item.path} title={collapsed ? item.label : ''} placement="right">
                <ListItemButton
                  component={Link}
                  to={item.path}
                  aria-label={item.label}
                  aria-current={matchesNavigation(item, location.pathname) ? 'page' : undefined}
                  onClick={onNavigate}
                  className="sis-sidebar__item"
                  sx={{ m: 0 }}
                >
                  <SvgIcon component={item.icon} className="sis-sidebar__icon" aria-hidden="true" />
                  <span className="sis-sidebar__label">{item.label}</span>
                  {item.items?.length > 1 && <span className="sis-sidebar__badge sis-sidebar__label">{item.items.length}</span>}
                </ListItemButton>
              </Tooltip>
            ))}
          </List>
        ))}
      </nav>
    </div>
  );
};

Sidebar.propTypes = {
  sections: PropTypes.arrayOf(PropTypes.shape({
    title: PropTypes.string.isRequired,
    items: PropTypes.arrayOf(PropTypes.shape({
      path: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      icon: PropTypes.elementType.isRequired,
      end: PropTypes.bool,
    })).isRequired,
  })).isRequired,
  collapsed: PropTypes.bool,
  onNavigate: PropTypes.func,
  branding: PropTypes.shape({ name: PropTypes.string, logo: PropTypes.string }),
  showBrand: PropTypes.bool,
  institution: PropTypes.string,
  workspaceLabel: PropTypes.string,
};
Sidebar.defaultProps = {
  collapsed: false,
  onNavigate: undefined,
  branding: undefined,
  showBrand: true,
  institution: '',
  workspaceLabel: '',
};

export default Sidebar;
