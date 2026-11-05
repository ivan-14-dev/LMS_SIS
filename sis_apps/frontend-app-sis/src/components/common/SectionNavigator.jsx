import React from 'react';
import PropTypes from 'prop-types';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Card, Typography,
} from '@mui/material';
import { ArrowBack, ArrowForward, TableChartOutlined } from '@mui/icons-material';

const SectionNavigator = ({ label, sections }) => {
  const [parameters] = useSearchParams();
  const location = useLocation();
  const selected = parameters.get('rubrique');
  const current = sections.find(section => section.id === selected);
  const destination = (id) => {
    const next = new URLSearchParams(parameters);
    if (id) { next.set('rubrique', id); } else { next.delete('rubrique'); }
    return { pathname: location.pathname, search: next.toString() };
  };
  if (sections.length === 1 && !selected) { return sections[0].content; }
  return (
    <Box className="sis-section-workspace">
      {current ? (
        <>
          <Box className="sis-section-workspace__heading">
            <Button component={Link} to={destination()} startIcon={<ArrowBack />}>Toutes les rubriques</Button>
            <Typography component="h2" variant="h2">{current.label}</Typography>
          </Box>
          <div key={current.id} className="sis-records-panel">{current.content}</div>
        </>
      ) : (
        <>
          {selected && <Alert severity="warning" sx={{ mb: 2 }}>Cette rubrique n’est pas disponible dans cet espace.</Alert>}
          {sections.length ? (
            <>
              <Typography color="text.secondary" sx={{ mb: 2 }}>Choisissez une rubrique pour consulter son contenu.</Typography>
              <nav className="sis-section-entries" aria-label={label}>
                {sections.map(section => (
                  <Card component={Link} to={destination(section.id)} key={section.id} className="sis-section-entry" aria-label={section.label}>
                    <TableChartOutlined className="sis-section-entry__icon" />
                    <Typography component="span" fontWeight={500}>{section.label}</Typography>
                    <ArrowForward fontSize="small" />
                  </Card>
                ))}
              </nav>
            </>
          ) : <Alert severity="info">Aucune rubrique accessible dans cet espace.</Alert>}
        </>
      )}
    </Box>
  );
};

SectionNavigator.propTypes = {
  label: PropTypes.string.isRequired,
  sections: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    content: PropTypes.node.isRequired,
  })).isRequired,
};

export default SectionNavigator;
