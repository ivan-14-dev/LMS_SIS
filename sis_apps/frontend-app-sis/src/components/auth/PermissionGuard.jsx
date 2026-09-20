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

const getNestedValue = (object, path) => path.split('.').reduce(
  (current, segment) => (current && current[segment] !== undefined ? current[segment] : undefined),
  object,
);

const matchesExpectedValue = (actual, expected) => {
  if (Array.isArray(expected)) {
    return Array.isArray(actual)
      ? actual.some((value) => expected.includes(value))
      : expected.includes(actual);
  }
  if (Array.isArray(actual)) {
    return actual.includes(expected);
  }
  return actual === expected;
};

const hasRequiredAttributes = (attributes, requiredAttributes = {}) => Object.entries(requiredAttributes).every(
  ([path, expected]) => matchesExpectedValue(getNestedValue(attributes, path), expected),
);

const PermissionGuard = ({
  type,
  permission,
  allowedRoles = [],
  allowedGroups = [],
  requiredAttributes = {},
  children,
}) => {
  const { data, isLoading, isError } = useCapabilities(type);

  if (isLoading) {
    return <Spinner animation="border" screenReaderText="Chargement des permissions" />;
  }
  const permissions = data?.permissions || [];
  const groups = data?.groups || [];
  const hasBasePermission = permissions.includes('*')
    || permissions.includes(permission)
    || allowedRoles.includes(data?.role);
  const hasRequiredGroup = !allowedGroups.length || allowedGroups.some((group) => groups.includes(group));
  const hasRequiredAttributeSet = hasRequiredAttributes(data?.attributes || {}, requiredAttributes);
  if (isError || !hasBasePermission || !hasRequiredGroup || !hasRequiredAttributeSet) {
    return <Alert variant="danger">Vous n’avez pas la permission d’accéder à ce module.</Alert>;
  }
  return children;
};

PermissionGuard.propTypes = {
  type: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  permission: PropTypes.string.isRequired,
  allowedRoles: PropTypes.arrayOf(PropTypes.string),
  allowedGroups: PropTypes.arrayOf(PropTypes.string),
  requiredAttributes: PropTypes.object,
  children: PropTypes.node.isRequired,
};

export default PermissionGuard;
