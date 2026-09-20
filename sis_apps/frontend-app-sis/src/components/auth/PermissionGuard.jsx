import React from 'react';
import PropTypes from 'prop-types';
import { useQuery } from '@tanstack/react-query';
import { Alert, Spinner } from '@openedx/paragon';

import {
  fetchApi,
  getSecondaireApiUrl,
  getSuperieurApiUrl,
} from '../../services/api';

export const useCapabilities = (type) => useQuery({
  queryKey: ['capabilities', type],
  queryFn: () => {
    const baseUrl = type === 'secondaire' ? getSecondaireApiUrl() : getSuperieurApiUrl();
    return fetchApi(`${baseUrl}/utilisateurs/comptes/capabilities/`);
  },
  staleTime: 60_000,
});

const PermissionGuard = ({
  type, permission, allowedRoles, children,
}) => {
  const { data, isLoading, isError } = useCapabilities(type);

  if (isLoading) {
    return <Spinner animation="border" screenReaderText="Chargement des permissions" />;
  }
  const permissions = data?.permissions || [];
  const allowed = permissions.includes('*')
    || permissions.includes(permission)
    || allowedRoles.includes(data?.role);
  if (isError || !allowed) {
    return <Alert variant="danger">Vous n’avez pas la permission d’accéder à ce module.</Alert>;
  }
  return children;
};

PermissionGuard.propTypes = {
  type: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  permission: PropTypes.string.isRequired,
  allowedRoles: PropTypes.arrayOf(PropTypes.string),
  children: PropTypes.node.isRequired,
};

PermissionGuard.defaultProps = {
  allowedRoles: [],
};

export default PermissionGuard;
