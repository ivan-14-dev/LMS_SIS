import React from 'react';
import PropTypes from 'prop-types';
import { Box, Typography, Button, Breadcrumbs, Link, IconButton } from '@mui/material';
import { ArrowBack as ArrowBackIcon, NavigateNext as NavigateNextIcon } from '@mui/icons-material';
import { useNavigate, Link as RouterLink } from 'react-router-dom';

const PageHeader = ({
  title,
  subtitle,
  breadcrumbs,
  actions,
  showBack,
}) => {
  const navigate = useNavigate();

  // Handle actions - can be React elements or array of config objects
  const renderActions = () => {
    if (!actions) return null;
    
    // If actions is a React element (single or fragment), render directly
    if (React.isValidElement(actions)) {
      return actions;
    }
    
    // If actions is an array
    if (Array.isArray(actions)) {
      return actions.map((action, index) => {
        // If array item is a React element, render it
        if (React.isValidElement(action)) {
          return React.cloneElement(action, { key: index });
        }
        // If array item is a config object, create a Button
        if (action && typeof action === 'object' && action.label) {
          return (
            <Button
              key={index}
              variant={action.variant === 'primary' ? 'contained' : 'outlined'}
              color={action.variant === 'danger' ? 'error' : 'primary'}
              startIcon={action.icon}
              onClick={action.onClick}
              size="large"
            >
              {action.label}
            </Button>
          );
        }
        return null;
      });
    }
    
    return null;
  };

  return (
    <Box sx={{ mb: 4 }}>
      {/* Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs 
          separator={<NavigateNextIcon fontSize="small" />} 
          sx={{ mb: 2 }}
        >
          {breadcrumbs.map((crumb, index) => (
            index < breadcrumbs.length - 1 ? (
              <Link
                key={index}
                component={RouterLink}
                to={crumb.path}
                underline="hover"
                color="inherit"
              >
                {crumb.label}
              </Link>
            ) : (
              <Typography key={index} color="text.primary">
                {crumb.label}
              </Typography>
            )
          ))}
        </Breadcrumbs>
      )}
      
      {/* Header content */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'flex-start',
        flexWrap: 'wrap',
        gap: 2,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {showBack && (
            <IconButton onClick={() => navigate(-1)} color="primary">
              <ArrowBackIcon />
            </IconButton>
          )}
          <Box>
            <Typography variant="h4" component="h1" fontWeight={700}>
              {title}
            </Typography>
            {subtitle && (
              <Typography variant="body1" color="text.secondary" sx={{ mt: 0.5 }}>
                {subtitle}
              </Typography>
            )}
          </Box>
        </Box>
        
        {actions && (
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {renderActions()}
          </Box>
        )}
      </Box>
    </Box>
  );
};

PageHeader.propTypes = {
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
  breadcrumbs: PropTypes.arrayOf(PropTypes.shape({
    label: PropTypes.string.isRequired,
    path: PropTypes.string,
  })),
  actions: PropTypes.oneOfType([
    PropTypes.node,
    PropTypes.arrayOf(PropTypes.oneOfType([
      PropTypes.node,
      PropTypes.shape({
        label: PropTypes.string.isRequired,
        icon: PropTypes.node,
        variant: PropTypes.string,
        onClick: PropTypes.func,
      }),
    ])),
  ]),
  showBack: PropTypes.bool,
};

PageHeader.defaultProps = {
  subtitle: null,
  breadcrumbs: null,
  actions: null,
  showBack: false,
};

export default PageHeader;
