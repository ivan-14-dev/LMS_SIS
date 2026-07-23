import React, { useState } from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Menu,
  MenuItem,
  Badge,
  Tooltip,
  Collapse,
  useTheme,
  useMediaQuery,
  Chip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  ChevronLeft as ChevronLeftIcon,
  Dashboard as DashboardIcon,
  People as PeopleIcon,
  School as SchoolIcon,
  Assignment as AssignmentIcon,
  Grade as GradeIcon,
  EventNote as EventNoteIcon,
  AccountBalance as AccountBalanceIcon,
  AttachMoney as MoneyIcon,
  CalendarMonth as CalendarIcon,
  Work as WorkIcon,
  MenuBook as MenuBookIcon,
  Flight as FlightIcon,
  LocalLibrary as LibraryIcon,
  Gavel as GavelIcon,
  Description as DescriptionIcon,
  CardGiftcard as CardGiftcardIcon,
  Notifications as NotificationsIcon,
  Settings as SettingsIcon,
  Logout as LogoutIcon,
  Person as PersonIcon,
  ExpandLess,
  ExpandMore,
  CloudSync as CloudSyncIcon,
  Business as BusinessIcon,
  AdminPanelSettings as AdminIcon,
  Group as GroupIcon,
  AccountTree as AccountTreeIcon,
  ChildCare as ChildCareIcon,
  Class as ClassIcon,
  Assessment as AssessmentIcon,
  EventAvailable as EventAvailableIcon,
  Restaurant as RestaurantIcon,
  DirectionsBus as DirectionsBusIcon,
  LocalHospital as LocalHospitalIcon,
  Hotel as HotelIcon,
  SportsEsports as SportsIcon,
  Groups as GroupsIcon,
} from '@mui/icons-material';

const drawerWidth = 260;
const collapsedDrawerWidth = 72;

// Navigation configuration for Supérieur
const superieurNav = [
  {
    title: 'Gestion Académique',
    items: [
      { text: 'Étudiants', icon: <PeopleIcon />, path: '/superieur/etudiants' },
      { text: 'Formations', icon: <SchoolIcon />, path: '/superieur/formations' },
      { text: 'Inscriptions', icon: <AssignmentIcon />, path: '/superieur/inscriptions' },
      { text: 'Notes', icon: <GradeIcon />, path: '/superieur/notes' },
      { text: 'Examens', icon: <EventNoteIcon />, path: '/superieur/examens' },
      { text: 'Jurys', icon: <GavelIcon />, path: '/superieur/jurys' },
      { text: 'Relevés', icon: <DescriptionIcon />, path: '/superieur/releves' },
      { text: 'Diplômes', icon: <CardGiftcardIcon />, path: '/superieur/diplomes' },
    ],
  },
  {
    title: 'Vie Étudiante',
    items: [
      { text: 'Bourses', icon: <MoneyIcon />, path: '/superieur/bourses' },
      { text: 'Emploi du temps', icon: <CalendarIcon />, path: '/superieur/emploi-du-temps' },
      { text: 'Stages', icon: <WorkIcon />, path: '/superieur/stages' },
      { text: 'Mémoires', icon: <MenuBookIcon />, path: '/superieur/memoires' },
      { text: 'Mobilité', icon: <FlightIcon />, path: '/superieur/mobilite' },
      { text: 'Bibliothèque', icon: <LibraryIcon />, path: '/superieur/bibliotheque' },
    ],
  },
  {
    title: 'Personnel',
    items: [
      { text: 'Enseignants', icon: <PersonIcon />, path: '/superieur/enseignants' },
      { text: 'Recherche', icon: <MenuBookIcon />, path: '/superieur/recherche' },
    ],
  },
  {
    title: 'Finances',
    items: [
      { text: 'Paiements', icon: <AccountBalanceIcon />, path: '/superieur/paiements' },
    ],
  },
];

// Navigation configuration for Secondaire
const secondaireNav = [
  {
    title: 'Gestion Scolaire',
    items: [
      { text: 'Élèves', icon: <ChildCareIcon />, path: '/secondaire/eleves' },
      { text: 'Classes', icon: <ClassIcon />, path: '/secondaire/classes' },
      { text: 'Évaluations', icon: <AssessmentIcon />, path: '/secondaire/evaluations' },
      { text: 'Bulletins', icon: <DescriptionIcon />, path: '/secondaire/bulletins' },
      { text: 'Présences', icon: <EventAvailableIcon />, path: '/secondaire/presences' },
      { text: 'Discipline', icon: <GavelIcon />, path: '/secondaire/discipline' },
    ],
  },
  {
    title: 'Services',
    items: [
      { text: 'Cantine', icon: <RestaurantIcon />, path: '/secondaire/cantine' },
      { text: 'Transport', icon: <DirectionsBusIcon />, path: '/secondaire/transport' },
      { text: 'Infirmerie', icon: <LocalHospitalIcon />, path: '/secondaire/infirmerie' },
      { text: 'Internat', icon: <HotelIcon />, path: '/secondaire/internat' },
    ],
  },
  {
    title: 'Activités',
    items: [
      { text: 'Clubs', icon: <SportsIcon />, path: '/secondaire/clubs' },
      { text: 'Conseil de classe', icon: <GroupsIcon />, path: '/secondaire/conseil-classe' },
    ],
  },
];

// Navigation configuration for Admin
const adminNav = [
  {
    title: 'Administration',
    items: [
      { text: 'Établissement', icon: <BusinessIcon />, path: '/admin/etablissement' },
      { text: 'Années académiques', icon: <CalendarIcon />, path: '/admin/annees-academiques' },
      { text: 'Intégration LMS', icon: <CloudSyncIcon />, path: '/admin/integration-lms' },
      { text: 'Utilisateurs', icon: <GroupIcon />, path: '/admin/utilisateurs' },
      { text: 'Structure', icon: <AccountTreeIcon />, path: '/admin/structure' },
    ],
  },
];

const ModernLayout = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const location = useLocation();
  
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const [expandedSections, setExpandedSections] = useState({});

  const currentDrawerWidth = collapsed ? collapsedDrawerWidth : drawerWidth;

  // Determine which module we're in
  const getModule = () => {
    if (location.pathname.startsWith('/secondaire')) return 'secondaire';
    if (location.pathname.startsWith('/admin')) return 'admin';
    return 'superieur';
  };
  
  const currentModule = getModule();
  const navConfig = currentModule === 'secondaire' ? secondaireNav 
    : currentModule === 'admin' ? adminNav 
    : superieurNav;

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleMenuOpen = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleSectionToggle = (title) => {
    setExpandedSections(prev => ({
      ...prev,
      [title]: !prev[title],
    }));
  };

  const isActivePath = (path) => location.pathname === path || location.pathname.startsWith(path + '/');

  const moduleColors = {
    superieur: theme.palette.primary.main,
    secondaire: theme.palette.secondary.main,
    admin: theme.palette.warning.main,
  };

  const moduleLabels = {
    superieur: 'Supérieur',
    secondaire: 'Secondaire',
    admin: 'Administration',
  };

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Logo Section */}
      <Box sx={{ 
        p: collapsed ? 1.5 : 2, 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: collapsed ? 'center' : 'flex-start',
        gap: 1.5,
        borderBottom: '1px solid',
        borderColor: 'divider',
        minHeight: 64,
      }}>
        <Avatar 
          sx={{ 
            width: 40, 
            height: 40, 
            bgcolor: moduleColors[currentModule],
            fontSize: '1rem',
            fontWeight: 700,
          }}
        >
          SIS
        </Avatar>
        {!collapsed && (
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'text.primary', lineHeight: 1.2 }}>
              SIS
            </Typography>
            <Typography variant="caption" sx={{ color: moduleColors[currentModule], fontWeight: 600 }}>
              {moduleLabels[currentModule]}
            </Typography>
          </Box>
        )}
      </Box>

      {/* Collapse Toggle */}
      {!isMobile && (
        <Box sx={{ p: 1, display: 'flex', justifyContent: collapsed ? 'center' : 'flex-end' }}>
          <IconButton 
            size="small" 
            onClick={() => setCollapsed(!collapsed)}
            sx={{ 
              bgcolor: 'action.hover',
              '&:hover': { bgcolor: 'action.selected' }
            }}
          >
            {collapsed ? <MenuIcon fontSize="small" /> : <ChevronLeftIcon fontSize="small" />}
          </IconButton>
        </Box>
      )}

      {/* Module Switcher */}
      <Box sx={{ 
        px: collapsed ? 1 : 2, 
        py: 1, 
        display: 'flex', 
        flexDirection: collapsed ? 'column' : 'row',
        gap: 0.5,
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}>
        {['superieur', 'secondaire', 'admin'].map((mod) => (
          <Tooltip key={mod} title={moduleLabels[mod]} placement="right">
            <IconButton
              size="small"
              onClick={() => navigate(`/${mod}`)}
              sx={{
                bgcolor: currentModule === mod ? moduleColors[mod] + '20' : 'transparent',
                color: currentModule === mod ? moduleColors[mod] : 'text.secondary',
                borderRadius: 1,
                '&:hover': { bgcolor: moduleColors[mod] + '15' },
              }}
            >
              {mod === 'superieur' && <SchoolIcon fontSize="small" />}
              {mod === 'secondaire' && <ChildCareIcon fontSize="small" />}
              {mod === 'admin' && <AdminIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        ))}
      </Box>

      {/* Dashboard Link */}
      <List sx={{ px: 1, py: 0.5 }} dense>
        <ListItem disablePadding>
          <Tooltip title={collapsed ? "Tableau de bord" : ""} placement="right">
            <ListItemButton
              onClick={() => navigate(`/${currentModule}`)}
              selected={location.pathname === `/${currentModule}`}
              sx={{ 
                borderRadius: 1, 
                py: 1,
                justifyContent: collapsed ? 'center' : 'flex-start',
                minHeight: 44,
              }}
            >
              <ListItemIcon sx={{ minWidth: collapsed ? 0 : 36, justifyContent: 'center' }}>
                <DashboardIcon 
                  fontSize="small"
                  color={location.pathname === `/${currentModule}` ? 'primary' : 'inherit'} 
                />
              </ListItemIcon>
              {!collapsed && (
                <ListItemText 
                  primary="Tableau de bord" 
                  primaryTypographyProps={{ fontSize: '0.875rem', fontWeight: 500 }}
                />
              )}
            </ListItemButton>
          </Tooltip>
        </ListItem>
      </List>

      <Divider />

      {/* Navigation Sections */}
      <Box sx={{ flexGrow: 1, overflowY: 'auto', overflowX: 'hidden', px: 1, py: 0.5 }}>
        {navConfig.map((section) => (
          <Box key={section.title} sx={{ mb: 0.5 }}>
            {!collapsed && (
              <ListItemButton
                onClick={() => handleSectionToggle(section.title)}
                sx={{ borderRadius: 1, py: 0.5, minHeight: 32 }}
                dense
              >
                <ListItemText 
                  primary={section.title} 
                  primaryTypographyProps={{ 
                    variant: 'caption', 
                    color: 'text.secondary',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}
                />
                {expandedSections[section.title] !== false ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
              </ListItemButton>
            )}
            <Collapse in={collapsed || expandedSections[section.title] !== false} timeout="auto" unmountOnExit>
              <List component="div" disablePadding dense>
                {section.items.map((item) => (
                  <ListItem key={item.path} disablePadding>
                    <Tooltip title={collapsed ? item.text : ""} placement="right">
                      <ListItemButton
                        onClick={() => {
                          navigate(item.path);
                          if (isMobile) setMobileOpen(false);
                        }}
                        selected={isActivePath(item.path)}
                        sx={{ 
                          borderRadius: 1, 
                          py: 0.75,
                          minHeight: 40,
                          justifyContent: collapsed ? 'center' : 'flex-start',
                          px: collapsed ? 1 : 2,
                        }}
                      >
                        <ListItemIcon sx={{ 
                          minWidth: collapsed ? 0 : 32, 
                          color: isActivePath(item.path) ? 'primary.main' : 'text.secondary',
                          justifyContent: 'center',
                        }}>
                          {React.cloneElement(item.icon, { fontSize: 'small' })}
                        </ListItemIcon>
                        {!collapsed && (
                          <ListItemText 
                            primary={item.text} 
                            primaryTypographyProps={{ 
                              fontSize: '0.8125rem',
                              fontWeight: isActivePath(item.path) ? 600 : 400,
                            }}
                          />
                        )}
                      </ListItemButton>
                    </Tooltip>
                  </ListItem>
                ))}
              </List>
            </Collapse>
          </Box>
        ))}
      </Box>

      {/* User Section */}
      <Box sx={{ 
        p: collapsed ? 1 : 1.5, 
        borderTop: '1px solid', 
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'flex-start',
        gap: 1.5,
      }}>
        <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: '0.875rem' }}>U</Avatar>
        {!collapsed && (
          <>
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography variant="body2" fontWeight={600} noWrap>Utilisateur</Typography>
              <Typography variant="caption" color="text.secondary" noWrap>Admin</Typography>
            </Box>
            <IconButton size="small">
              <LogoutIcon fontSize="small" />
            </IconButton>
          </>
        )}
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          width: { md: `calc(100% - ${currentDrawerWidth}px)` },
          ml: { md: `${currentDrawerWidth}px` },
          bgcolor: 'background.paper',
          color: 'text.primary',
          borderBottom: '1px solid',
          borderColor: 'divider',
          transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
            Système d'Information Scolaire
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tooltip title="Notifications">
              <IconButton color="inherit">
                <Badge badgeContent={3} color="error">
                  <NotificationsIcon />
                </Badge>
              </IconButton>
            </Tooltip>
            
            <Tooltip title="Paramètres">
              <IconButton color="inherit">
                <SettingsIcon />
              </IconButton>
            </Tooltip>

            <Tooltip title="Profil">
              <IconButton onClick={handleMenuOpen} sx={{ ml: 1 }}>
                <Avatar sx={{ width: 36, height: 36, bgcolor: 'primary.main' }}>U</Avatar>
              </IconButton>
            </Tooltip>
          </Box>

          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <MenuItem onClick={handleMenuClose}>
              <ListItemIcon><PersonIcon fontSize="small" /></ListItemIcon>
              Mon profil
            </MenuItem>
            <MenuItem onClick={handleMenuClose}>
              <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>
              Paramètres
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleMenuClose}>
              <ListItemIcon><LogoutIcon fontSize="small" /></ListItemIcon>
              Déconnexion
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Drawer */}
      <Box
        component="nav"
        sx={{ 
          width: { md: currentDrawerWidth }, 
          flexShrink: { md: 0 },
          transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        {/* Mobile drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        
        {/* Desktop drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': { 
              boxSizing: 'border-box', 
              width: currentDrawerWidth,
              transition: theme.transitions.create('width', {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.leavingScreen,
              }),
              overflowX: 'hidden',
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 2.5,
          width: { md: `calc(100% - ${currentDrawerWidth}px)` },
          mt: '64px',
          minHeight: 'calc(100vh - 64px)',
          transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
};

export default ModernLayout;
