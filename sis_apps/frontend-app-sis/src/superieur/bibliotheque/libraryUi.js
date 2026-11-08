import PropTypes from 'prop-types';

export const libraryQueryOptions = {
  retry: false,
  gcTime: 0,
  staleTime: 0,
  refetchOnMount: 'always',
  refetchOnWindowFocus: 'always',
};

export const reservationResource = variant => (variant === 'secondaire' ? 'reservations' : 'reservations-bibliotheque');

export const bookType = PropTypes.shape({
  id: PropTypes.number.isRequired,
  titre: PropTypes.string.isRequired,
  auteurs: PropTypes.string,
  resume: PropTypes.string,
  licence_active: PropTypes.bool,
  licence_reference: PropTypes.string,
  licence_expire_le: PropTypes.string,
  peut_consulter_ressource: PropTypes.bool,
});
