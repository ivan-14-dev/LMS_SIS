import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { getConfig } from '@edx/frontend-platform';
import {
  Link, NavLink, Navigate, Outlet, useLocation, useNavigate,
} from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Avatar, Button, Drawer, IconButton, Menu as AccountMenu, MenuItem, Tooltip, useMediaQuery,
} from '@mui/material';
import {
  Close, Menu, NotificationsNone, ExpandMore,
} from '@mui/icons-material';
import { fetchApi } from '../../services/api';
import { apiErrorMessage, getEnabledVariants, resourceUrl } from '../../services/resources';
import { useCapabilities } from '../auth/PermissionGuard';
import Sidebar, { WorkspaceBrand } from './Sidebar';
import LocalSessionGate from '../auth/LocalSessionGate';
import {
  getNavigation, getWorkspaceGroups, matchesNavigation, workspaceKind,
} from './navigation';
import AppearanceProvider from '../../theme/AppearanceProvider';
import WorkspaceTools, { navigationKey } from './WorkspaceTools';
import useWorkspacePreferences from './useWorkspacePreferences';

const labels = { secondaire: 'Secondaire', superieur: 'Supérieur' };

const Workspace = ({ type, variant }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const mobile = useMediaQuery('(max-width: 991px)');
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [accountAnchor, setAccountAnchor] = useState(null);
  const sso = getConfig().SIS_AUTH_MODE === 'lms';
  const capabilities = useCapabilities(variant);
  const profileUrl = resourceUrl(variant, 'utilisateurs/comptes');
  const profile = useQuery({
    queryKey: ['profile', profileUrl], queryFn: () => fetchApi(`${profileUrl}me/`),
  });
  const allowedCapabilities = capabilities.isError ? undefined : capabilities.data;
  const allSections = getNavigation(variant, variant, allowedCapabilities, location.search);
  const preferences = useWorkspacePreferences(profile.data?.id
    ? `${profileUrl}:${profile.data.etablissement}:${profile.data.id}` : null);
  const favorites = allSections.flatMap(section => section.items)
    .filter(item => preferences.favorites.includes(navigationKey(item)));
  const kind = workspaceKind(capabilities.data);
  const learner = kind === 'learner';
  const groups = getWorkspaceGroups(allSections, kind);
  const navigation = [
    { title: 'Menu', items: groups.filter(group => !group.admin) },
    { title: 'Établissement', items: groups.filter(group => group.admin) },
  ].filter(section => section.items.length);
  const activeGroup = groups.find(group => matchesNavigation(group, location.pathname));
  let workspaceLabel = 'Administration établissement';
  if (kind === 'teacher') { workspaceLabel = 'Enseignant / formateur'; }
  if (kind === 'learner') { workspaceLabel = capabilities.data.role === 'parent' ? 'Parent / tuteur' : 'Apprenant'; }
  const current = allSections.flatMap(section => section.items)
    .find(item => matchesNavigation(item, location.pathname));
  useEffect(() => { setMenuOpen(false); }, [location.pathname, location.search]);
  const changeVariant = (event) => {
    if (type === 'admin') {
      const parameters = new URLSearchParams(location.search);
      parameters.set('sis', event.target.value);
      navigate(`${location.pathname}?${parameters}`);
    } else {
      navigate(`/${event.target.value}`);
    }
  };
  const closeMenu = () => setMenuOpen(false);
  const desktopMenuLabel = collapsed ? 'Déployer le menu' : 'Réduire le menu';
  const account = (
    <>
      <Avatar className="sis-account-avatar" aria-hidden="true">
        {(profile.data?.full_name || profile.data?.username || 'S').slice(0, 1).toLocaleUpperCase('fr')}
      </Avatar>
      <span>
        <strong>{profile.data?.full_name || profile.data?.username || 'Mon compte'}</strong>
        <small>{profile.data?.role_display || capabilities.data?.role}</small>
      </span>
    </>
  );
  return (
    <AppearanceProvider mode={preferences.theme} brand={profile.data?.branding?.primary_color}>
      <div className={`sis-layout sis-layout--${learner ? 'learner' : 'management'}${collapsed && !mobile ? ' sis-layout--compact' : ''}`}>
        <a className="sis-skip-link" href="#sis-main">Aller au contenu</a>
        {mobile && (
        <Drawer
          open={menuOpen}
          onClose={closeMenu}
          slotProps={{
            paper: {
              id: 'sis-navigation', role: 'dialog', 'aria-modal': true, 'aria-label': 'Menu de navigation',
            },
          }}
        >
          <div className="sis-mobile-menu-heading">
            <strong>Navigation</strong>
            <IconButton onClick={closeMenu} aria-label="Fermer le menu"><Close /></IconButton>
          </div>
          <Sidebar
            sections={navigation}
            onNavigate={closeMenu}
            branding={profile.data?.branding}
            institution={profile.data?.etablissement_nom}
            workspaceLabel={workspaceLabel}
          />
        </Drawer>
        )}
        <header className="sis-topbar">
          <IconButton
            aria-label={mobile ? 'Ouvrir le menu' : desktopMenuLabel}
            aria-expanded={mobile ? menuOpen : !collapsed}
            aria-controls="sis-navigation"
            onClick={() => (mobile ? setMenuOpen(true) : setCollapsed(value => !value))}
          >
            <Menu />
          </IconButton>
          <Link to={`/${variant}`} className="sis-topbar__brand" aria-label="Retour à l’accueil">
            <WorkspaceBrand branding={profile.data?.branding} />
          </Link>
          <div className="sis-topbar__tools">
            <WorkspaceTools
              sections={allSections}
              preferences={preferences}
              brand={profile.data?.branding?.primary_color}
            />
            <label className="sis-context-select" htmlFor="sis-context">
              <span>Contexte SIS</span>
              <select id="sis-context" value={variant} onChange={changeVariant}>
                {getEnabledVariants().map(value => <option key={value} value={value}>{labels[value]}</option>)}
              </select>
            </label>
            <Tooltip title="Notifications">
              <IconButton component={Link} to={`/${variant}/workflows`} aria-label="Notifications">
                <NotificationsNone />
              </IconButton>
            </Tooltip>
            {sso ? (
              <>
                <Button
                  className="sis-account-link"
                  aria-label="Menu du compte"
                  aria-haspopup="menu"
                  aria-expanded={Boolean(accountAnchor)}
                  aria-controls={accountAnchor ? 'sis-account-menu' : undefined}
                  onClick={event => setAccountAnchor(event.currentTarget)}
                  endIcon={<ExpandMore />}
                >{account}
                </Button>
                <AccountMenu id="sis-account-menu" anchorEl={accountAnchor} open={Boolean(accountAnchor)} onClose={() => setAccountAnchor(null)}>
                  <MenuItem component={Link} to={`/${variant}/compte`} onClick={() => setAccountAnchor(null)}>Mon compte SIS</MenuItem>
                  <MenuItem component="a" href={`${getConfig().LMS_BASE_URL}/dashboard`}>Mes cours LMS</MenuItem>
                  <MenuItem component="a" href={`${getConfig().LMS_BASE_URL}/account/settings`}>Mon compte LMS</MenuItem>
                  <MenuItem component="a" href={getConfig().LOGOUT_URL}>Se déconnecter</MenuItem>
                </AccountMenu>
              </>
            ) : <Link to={`/${variant}/compte`} className="sis-account-link" aria-label="Ouvrir mon compte">{account}</Link>}
          </div>
        </header>
        <div className="sis-layout__workspace">
          {!mobile && (
            <aside id="sis-navigation" className="sis-layout__sidebar">
              <Sidebar
                sections={navigation}
                collapsed={collapsed}
                showBrand={false}
                institution={profile.data?.etablissement_nom || `SIS ${labels[variant]}`}
                workspaceLabel={workspaceLabel}
              />
            </aside>
          )}
          <div className="sis-layout__body">
            <main id="sis-main" tabIndex={-1} className="sis-content">
              {current && !current.end && current.path.split('?')[0] === location.pathname && (
              <nav aria-label="Fil d’Ariane" className="sis-breadcrumbs">
                <Link to={`/${variant}`}>Accueil</Link>
                {activeGroup && <><span aria-hidden="true">/</span><span>{activeGroup.label}</span></>}
                <span aria-hidden="true">/</span><span aria-current="page">{current.label}</span>
              </nav>
              )}
              {activeGroup && !activeGroup.home && activeGroup.items.length > 1 && (
              <nav aria-label={`Navigation de section : ${activeGroup.label}`} className="sis-section-nav">
                {activeGroup.items.map(item => (
                  <NavLink key={item.path} to={item.path}>{item.label}</NavLink>
                ))}
              </nav>
              )}
              {(capabilities.isError || profile.isError) && (
              <Alert
                severity="error"
                sx={{ mb: 2 }}
                action={<Button onClick={() => { capabilities.refetch(); profile.refetch(); }}>Réessayer</Button>}
              >
                Impossible de charger votre espace. {apiErrorMessage(capabilities.error || profile.error)}
              </Alert>
              )}
              {preferences.error && <Alert severity="warning" sx={{ mb: 2 }}>{preferences.error}</Alert>}
              <Outlet
                key={variant}
                context={{
                  variant,
                  sections: allSections,
                  groups,
                  favorites,
                  profile: profile.data,
                  capabilities: capabilities.isError ? undefined : capabilities.data,
                  loading: capabilities.isLoading,
                  error: capabilities.error,
                }}
              />
            </main>
            <footer className="sis-footer">
              <strong>LMS SIS</strong>
              <span>{profile.data?.etablissement_nom || 'Votre établissement'} · {labels[variant]}</span>
            </footer>
          </div>
        </div>
      </div>
    </AppearanceProvider>
  );
};
Workspace.propTypes = {
  type: PropTypes.oneOf(['superieur', 'secondaire', 'admin']).isRequired,
  variant: PropTypes.oneOf(['superieur', 'secondaire']).isRequired,
};

const SISLayout = ({ type }) => {
  const location = useLocation();
  const enabled = getEnabledVariants();
  const parameters = new URLSearchParams(location.search);
  const selected = parameters.get('sis');
  const variant = type === 'admin' ? selected : type;
  if (type !== 'admin' && !enabled.includes(type)) { return <Navigate to={`/${enabled[0]}`} replace />; }
  if (type === 'admin' && !enabled.includes(selected)) {
    parameters.set('sis', enabled[0]);
    return <Navigate to={`${location.pathname}?${parameters}`} replace />;
  }
  return (
    <LocalSessionGate key={variant} variant={variant}>
      <Workspace type={type} variant={variant} />
    </LocalSessionGate>
  );
};
SISLayout.propTypes = { type: PropTypes.oneOf(['superieur', 'secondaire', 'admin']).isRequired };

export default SISLayout;
