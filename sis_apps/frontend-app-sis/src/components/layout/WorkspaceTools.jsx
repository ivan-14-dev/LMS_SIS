import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton,
  List, ListItem, ListItemButton, ListItemText, MenuItem, Stack, Tab, Tabs, TextField, Tooltip, Typography,
} from '@mui/material';
import {
  Search, Star, StarBorder, Tune, DarkModeOutlined, LightModeOutlined,
} from '@mui/icons-material';
import { filterNavigation } from './navigation';
import { designTokens } from '../../theme/tokens';
import AcademicSearch from './AcademicSearch';
import { academicSearchResources } from '../../services/academicSearch';

export const navigationKey = item => item.path.split('?')[0];

const WorkspaceTools = ({
  sections, preferences, brand, variant, capabilities, searchContext,
}) => {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState(false);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('modules');
  const trigger = useRef(null);
  const list = useRef(null);
  const colors = designTokens(preferences.theme, brand);
  useEffect(() => {
    const shortcut = event => {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k'
        && !document.querySelector('[role="dialog"]')) {
        event.preventDefault();
        trigger.current?.focus();
        setQuery('');
        setMode('modules');
        setOpen(true);
      }
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, []);
  const close = () => setOpen(false);
  const favorite = item => preferences.favorites.includes(navigationKey(item));
  const toggle = item => preferences.update({
    favorites: favorite(item) ? preferences.favorites.filter(path => path !== navigationKey(item))
      : [...preferences.favorites, navigationKey(item)],
  });
  const moveFocus = event => {
    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) { return; }
    const links = [...(list.current?.querySelectorAll('a') || [])];
    if (!links.length) { return; }
    event.preventDefault();
    const index = links.indexOf(document.activeElement);
    const direction = event.key === 'ArrowDown' ? 1 : -1;
    const start = direction === 1 ? 0 : links.length - 1;
    const next = index < 0 ? start : (index + direction + links.length) % links.length;
    links[next].focus();
  };
  const visible = filterNavigation(sections, query);
  const resources = academicSearchResources(variant, capabilities);
  return (
    <>
      <Tooltip title="Rechercher un module ou un dossier (Ctrl+K / ⌘K)">
        <Button className="sis-search-trigger" ref={trigger} aria-label="Ouvrir la palette de navigation" aria-keyshortcuts="Control+k Meta+k" onClick={() => { setQuery(''); setMode('modules'); setOpen(true); }}>
          <Search /><span>Rechercher</span><kbd>Ctrl K</kbd>
        </Button>
      </Tooltip>
      <Tooltip title="Préférences d’affichage">
        <IconButton aria-label="Préférences d’affichage" onClick={() => setSettings(true)}><Tune /></IconButton>
      </Tooltip>
      <Tooltip
        title={preferences.theme === 'light' ? 'Passer au thème sombre' : 'Passer au thème clair'}
        disableHoverListener={!preferences.ready}
      >
        <IconButton
          aria-label={preferences.theme === 'light' ? 'Passer au thème sombre' : 'Passer au thème clair'}
          disabled={!preferences.ready}
          onClick={() => preferences.update({ theme: preferences.theme === 'light' ? 'dark' : 'light' })}
        >
          {preferences.theme === 'light' ? <DarkModeOutlined /> : <LightModeOutlined />}
        </IconButton>
      </Tooltip>
      <Dialog open={open} onClose={close} fullWidth aria-labelledby="sis-command-title">
        <DialogTitle id="sis-command-title">{mode === 'records' ? 'Recherche de dossiers' : 'Aller à un module'}</DialogTitle>
        <DialogContent onKeyDown={mode === 'modules' ? moveFocus : undefined}>
          {variant && (
            <Tabs value={mode} onChange={(_, value) => setMode(value)} aria-label="Portée de la recherche" sx={{ mb: 2 }}>
              <Tab value="modules" label="Modules" /><Tab value="records" label="Dossiers" />
            </Tabs>
          )}
          {mode === 'records' && open && variant && (
            searchContext ? (
              <AcademicSearch
                key={searchContext}
                variant={variant}
                resources={resources}
                onNavigate={close}
              />
            ) : <Alert severity="info">Vérification de vos accès avant la recherche…</Alert>
          )}
          {mode === 'modules' && (
            <>
              <TextField
                autoFocus
                fullWidth
                label="Rechercher dans les modules autorisés"
                value={query}
                onChange={event => setQuery(event.target.value)}
                helperText="Flèches pour parcourir, Entrée pour ouvrir, Tab pour les favoris, Échap pour fermer."
              />
              <Typography variant="body2" sx={{ mt: 2 }}>Navigation uniquement : aucune recherche dans les dossiers personnels.</Typography>
              <Box ref={list}>
                {visible.map(section => (
                  <Box key={section.title} component="section" aria-label={section.title}>
                    <Typography component="h3" variant="subtitle2" sx={{ mt: 2 }}>{section.title}</Typography>
                    <List disablePadding>
                      {section.items.map(item => (
                        <ListItem
                          key={item.path}
                          disablePadding
                          secondaryAction={(
                            <IconButton
                              aria-label={`${favorite(item) ? 'Retirer' : 'Ajouter'} ${item.label} ${favorite(item) ? 'des' : 'aux'} favoris`}
                              aria-pressed={favorite(item)}
                              disabled={!preferences.ready}
                              onClick={() => toggle(item)}
                            >
                              {favorite(item) ? <Star color="primary" /> : <StarBorder />}
                            </IconButton>
                      )}
                        >
                          <ListItemButton component={Link} to={item.path} onClick={close} sx={{ mr: 6 }}>
                            <ListItemText primary={item.label} />
                          </ListItemButton>
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                ))}
              </Box>
              {!visible.length && <Typography role="status" sx={{ mt: 2 }}>Aucun module autorisé ne correspond.</Typography>}
            </>
          )}
        </DialogContent>
        <DialogActions><Button onClick={close}>Fermer la palette</Button></DialogActions>
      </Dialog>
      <Dialog open={settings} onClose={() => setSettings(false)} fullWidth aria-labelledby="sis-preferences-title">
        <DialogTitle id="sis-preferences-title">Préférences d’affichage</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <Typography>
              Préférences propres à ce compte et à cet établissement sur cet appareil. Aucun changement de droits.
            </Typography>
            <Typography>
              La charte ERP est commune à tous les espaces. Le logo et la couleur du monogramme
              identifient votre établissement sans modifier les couleurs des actions.
            </Typography>
            <TextField
              select
              label="Thème"
              value={preferences.theme}
              disabled={!preferences.ready}
              onChange={event => preferences.update({ theme: event.target.value })}
            >
              <MenuItem value="light">Clair</MenuItem><MenuItem value="dark">Sombre</MenuItem>
            </TextField>
            {colors.brandAdjusted && (
              <Alert severity="info">
                La couleur institutionnelle est ajustée à l’écran pour préserver un contraste lisible.
              </Alert>
            )}
            {colors.invalidBrand && <Alert severity="warning">Couleur institutionnelle invalide : la couleur du produit est utilisée.</Alert>}
            <Typography>
              Retrouvez vos favoris sur l’accueil et dans la palette de navigation.
              Un module retiré de vos droits ne reste pas accessible par un favori.
            </Typography>
            <Button
              disabled={!preferences.ready || !preferences.favorites.length}
              onClick={() => preferences.update({ favorites: [] })}
            >
              Effacer mes favoris sur cet appareil
            </Button>
            {preferences.error && <Alert severity="warning">{preferences.error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions><Button onClick={() => setSettings(false)}>Fermer les préférences</Button></DialogActions>
      </Dialog>
    </>
  );
};
WorkspaceTools.propTypes = {
  sections: PropTypes.arrayOf(PropTypes.shape({
    title: PropTypes.string.isRequired,
    items: PropTypes.arrayOf(PropTypes.shape({
      path: PropTypes.string.isRequired, label: PropTypes.string.isRequired,
    })).isRequired,
  })).isRequired,
  preferences: PropTypes.shape({
    theme: PropTypes.string.isRequired,
    favorites: PropTypes.arrayOf(PropTypes.string).isRequired,
    update: PropTypes.func.isRequired,
    ready: PropTypes.bool.isRequired,
    error: PropTypes.string.isRequired,
  }).isRequired,
  brand: PropTypes.string,
  variant: PropTypes.oneOf(['secondaire', 'superieur']),
  capabilities: PropTypes.shape({
    role: PropTypes.string,
    permissions: PropTypes.arrayOf(PropTypes.string),
  }),
  searchContext: PropTypes.string,
};
WorkspaceTools.defaultProps = {
  brand: undefined, variant: undefined, capabilities: undefined, searchContext: null,
};
export default WorkspaceTools;
