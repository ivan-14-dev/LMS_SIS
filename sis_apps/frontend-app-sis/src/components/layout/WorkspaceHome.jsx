import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Link, useOutletContext } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, CircularProgress, IconButton, SvgIcon, Tab, Tabs, Typography,
} from '@mui/material';
import {
  ArrowForward, ChevronLeft, ChevronRight, TodayOutlined, PersonOutline, GridViewOutlined,
} from '@mui/icons-material';
import { fetchApi } from '../../services/api';
import { fetchResourcePage, resourceUrl } from '../../services/resources';
import { workspaceKind } from './navigation';
import WorkspaceCalendar from './WorkspaceCalendar';
import WorkflowNotificationsPanel from '../common/WorkflowNotificationsPanel';

const moduleShape = PropTypes.shape({
  label: PropTypes.string.isRequired,
  path: PropTypes.string.isRequired,
  resource: PropTypes.string,
  description: PropTypes.string,
  icon: PropTypes.elementType.isRequired,
});

const PersonalSummary = ({ variant, staff }) => {
  const summary = useQuery({
    queryKey: ['workspace-personal', variant, staff],
    queryFn: () => fetchApi(resourceUrl(variant, `portail/${staff ? 'staff' : 'apprenant'}/tableau_bord`)),
  });
  if (summary.isLoading) { return <span role="status">Chargement de votre dossier…</span>; }
  if (summary.isError) {
    return (
      <Alert severity="error" action={<Button onClick={() => summary.refetch()}>Réessayer</Button>}>
        Impossible de charger votre dossier.
      </Alert>
    );
  }
  const stats = summary.data?.statistiques;
  const person = summary.data?.eleve || summary.data?.etudiant;
  let indicators = [['Moyenne', stats?.moyenne], ['Crédits validés', stats?.credits_valides]];
  if (variant === 'secondaire') { indicators = [['Moyenne', stats?.moyenne], ['Absences', stats?.absences]]; }
  if (summary.data?.enfants) { indicators = [['Enfants autorisés', summary.data.enfants.length]]; }
  if (staff) {
    indicators = variant === 'secondaire'
      ? [['Classes', stats?.nb_classes], ['Élèves suivis', stats?.nb_eleves_total]]
      : [['Cours', stats?.nb_cours], ['Heures', stats?.heures_total]];
  }
  return (
    <div className="sis-module-card__personal">
      {person?.nom && <p>{person.nom}{summary.data?.classe?.nom ? ` · ${summary.data.classe.nom}` : ''}</p>}
      <dl>{indicators.map(([label, value]) => (
        <div key={label}><dt>{label}</dt><dd>{value ?? '—'}</dd></div>
      ))}
      </dl>
    </div>
  );
};
PersonalSummary.propTypes = { variant: PropTypes.string.isRequired, staff: PropTypes.bool.isRequired };

const ModuleCard = ({ item, variant }) => {
  const count = useQuery({
    queryKey: ['workspace-count', variant, item.resource],
    queryFn: () => fetchResourcePage(resourceUrl(variant, item.resource), { page_size: 1 }),
    enabled: Boolean(item.resource),
  });
  const personal = /\/portail-(apprenant|staff)$/.test(item.path);
  return (
    <article className="sis-module-card">
      <div className="sis-module-card__meta">
        <span className="sis-module-card__icon"><SvgIcon component={item.icon} /></span>
        <span className="sis-module-card__tag">{personal ? 'Mon suivi' : 'Accès autorisé'}</span>
      </div>
      <h3><Link to={item.path}>{item.label}</Link></h3>
      <p>{item.description || 'Consultez vos informations et les actions disponibles dans cet espace.'}</p>
      {personal && <PersonalSummary variant={variant} staff={item.path.endsWith('/portail-staff')} />}
      {item.resource && (
        <div className="sis-module-card__count">
          {count.isLoading && <span role="status">Chargement du compteur…</span>}
          {count.isError && (
            <>
              <span role="alert">Compteur indisponible.</span>
              <Button size="small" onClick={() => count.refetch()}>Réessayer le compteur</Button>
            </>
          )}
          {count.data && !count.isError && (
            <><strong>{count.data.count.toLocaleString('fr')}</strong><span>Dossiers accessibles</span></>
          )}
        </div>
      )}
      <Link className="sis-module-card__open" to={item.path}>Ouvrir {item.label}<ArrowForward fontSize="small" /></Link>
    </article>
  );
};
ModuleCard.propTypes = { variant: PropTypes.string.isRequired, item: moduleShape.isRequired };

const WorkspaceHome = () => {
  const {
    variant, sections, groups, favorites, profile, capabilities, loading, error,
  } = useOutletContext();
  const [selected, setSelected] = useState('overview');
  const [page, setPage] = useState(0);
  if (loading) { return <CircularProgress aria-label="Chargement de votre espace" />; }
  if (error || !capabilities) { return <Alert severity="error">Votre espace ne peut pas être chargé pour le moment.</Alert>; }
  const kind = workspaceKind(capabilities);
  const modules = sections.filter(section => section.title !== 'Compte').map(section => ({
    ...section, items: section.items.filter(item => !item.end),
  })).filter(section => section.items.length);
  const items = modules.flatMap(section => section.items);
  const spotlight = [...items.filter(item => /\/portail-(apprenant|staff)$/.test(item.path)), ...items.filter(item => item.resource)];
  const overview = [...spotlight, ...items.filter(item => !spotlight.includes(item))];
  const tabs = [{ title: 'overview', label: 'À la une', items: overview }, ...modules];
  const current = tabs.find(tab => tab.title === selected) || tabs[0];
  const lastPage = Math.max(0, Math.ceil(current.items.length / 2) - 1);
  const currentPage = Math.min(page, lastPage);
  const today = new Date();
  let title = 'Votre espace de travail';
  if (kind === 'teacher') { title = 'Mon activité pédagogique'; }
  if (kind === 'learner') {
    title = variant === 'secondaire' ? 'Mon espace élève' : 'Mon espace étudiant';
    if (capabilities.role === 'parent') { title = 'Mon espace famille'; }
  }
  return (
    <div className="sis-erp-home">
      <header className="sis-welcome">
        <div>
          <p className="sis-eyebrow">Mon établissement <span aria-hidden="true">/</span> Tableau de bord</p>
          <div className="sis-welcome__title"><h1>{title}</h1><span className="sis-role-badge">{profile?.role_display || capabilities.role}</span></div>
          <p>{profile?.full_name ? `Bonjour ${profile.full_name}. ` : ''}Vos cours, vos dossiers et votre suivi, au même endroit.</p>
        </div>
        <time dateTime={`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`}>
          {new Intl.DateTimeFormat('fr', { dateStyle: 'full' }).format(today)}
        </time>
      </header>
      {favorites.length > 0 && (
        <nav className="sis-favorites" aria-label="Favoris">
          <strong>Favoris</strong>
          {favorites.map(item => <Link key={item.path} to={item.path}>{item.label}</Link>)}
        </nav>
      )}
      <div className="sis-home-grid">
        <section className="sis-home-modules" aria-label="Modules disponibles">
          <Tabs
            value={current.title}
            onChange={(_, value) => { setSelected(value); setPage(0); }}
            variant="scrollable"
            scrollButtons="auto"
            aria-label="Catégories de modules"
          >
            {tabs.map((tab, index) => (
              <Tab key={tab.title} value={tab.title} label={tab.label || tab.title} id={`module-tab-${index}`} aria-controls="module-panel" />
            ))}
          </Tabs>
          <div role="tabpanel" id="module-panel" aria-labelledby={`module-tab-${tabs.indexOf(current)}`}>
            <div className="sis-module-grid">
              {current.items.slice(currentPage * 2, currentPage * 2 + 2).map(item => (
                <ModuleCard key={item.path} variant={variant} item={item} />
              ))}
            </div>
            {!current.items.length && <Alert severity="info">Aucun module n’est attribué à votre compte.</Alert>}
          </div>
          {current.items.length > 2 && (
            <div className="sis-module-pagination">
              <span aria-live="polite">{currentPage * 2 + 1}–{Math.min(currentPage * 2 + 2, current.items.length)} sur {current.items.length} modules</span>
              <IconButton aria-label="Modules précédents" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}><ChevronLeft /></IconButton>
              <IconButton aria-label="Modules suivants" disabled={currentPage === lastPage} onClick={() => setPage(currentPage + 1)}><ChevronRight /></IconButton>
            </div>
          )}
        </section>
        <WorkspaceCalendar />
        <section className="sis-home-spaces sis-panel" aria-labelledby="sis-spaces-title">
          <div className="sis-widget-heading"><GridViewOutlined /><h2 id="sis-spaces-title">Vos espaces</h2></div>
          <div className="sis-space-list">
            {groups.filter(group => !group.home).map(group => (
              <Link key={group.id} to={group.path} className="sis-space-link">
                <SvgIcon component={group.icon} aria-hidden="true" />
                <span><strong>{group.label}</strong></span>
                <small aria-label={`${group.items.length} rubriques accessibles`}>{group.items.length}</small>
                <ArrowForward fontSize="small" />
              </Link>
            ))}
          </div>
        </section>
        <section className="sis-home-notifications" aria-label="Suivi personnel">
          <WorkflowNotificationsPanel apiType={variant} title="À consulter" />
        </section>
        <aside className="sis-home-widgets" aria-label="Repères personnels">
          <section className="sis-pastel-widget sis-pastel-widget--lavender">
            <div className="sis-widget-heading"><TodayOutlined /><h2>Aujourd’hui</h2></div>
            <strong className="sis-day-number">{today.getDate()}</strong>
            <span>{new Intl.DateTimeFormat('fr', { month: 'long', year: 'numeric' }).format(today)}</span>
            <small>Échéances dans vos modules.</small>
          </section>
          <section className="sis-pastel-widget sis-pastel-widget--pink">
            <div className="sis-widget-heading"><PersonOutline /><h2>Mon profil</h2></div>
            <Typography fontWeight={600}>{profile?.full_name || profile?.username || 'Mon compte'}</Typography>
            <p>{profile?.role_display || capabilities.role}</p>
            <Button component={Link} to={`/${variant}/compte`} endIcon={<ArrowForward />} size="small">Gérer mon compte</Button>
          </section>
        </aside>
      </div>
    </div>
  );
};

export default WorkspaceHome;
