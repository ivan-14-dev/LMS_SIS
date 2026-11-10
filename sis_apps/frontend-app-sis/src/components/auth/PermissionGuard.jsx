import React from 'react';
import PropTypes from 'prop-types';
import { useQuery } from '@tanstack/react-query';
import { Alert, Spinner } from '@openedx/paragon';

import {
  fetchApi,
  getSecondaireApiUrl,
  getSuperieurApiUrl,
} from '../../services/api';
import { canEnterPortal, hasCapability } from '../layout/navigation';
import { getActiveRole } from '../../services/roleContext';

export const useCapabilities = (type, options = {}) => {
  const baseUrl = type === 'secondaire' ? getSecondaireApiUrl() : getSuperieurApiUrl();
  const role = getActiveRole(baseUrl);
  return useQuery({
    queryKey: role ? ['capabilities', type, role] : ['capabilities', type],
    queryFn: () => fetchApi(`${baseUrl}/utilisateurs/comptes/capabilities/`),
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    ...options,
  });
};

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
  allowedGroups = [],
  requiredAttributes = {},
  portal,
  children,
}) => {
  const {
    data, isLoading, isFetching, isError,
  } = useCapabilities(type);

  if (isLoading || isFetching) {
    return <Spinner animation="border" screenReaderText="Chargement des permissions" />;
  }
  if (isError || !data) {
    return <Alert variant="danger">Impossible de vérifier vos permissions. Rechargez la page pour réessayer.</Alert>;
  }
  if (portal && !(Array.isArray(portal) ? portal : [portal]).some(kind => canEnterPortal(data, kind))) {
    return <Alert variant="danger">Vous n’avez pas accès à ce portail pour votre affiliation actuelle.</Alert>;
  }
  const groups = data?.groups || [];
  const hasBasePermission = portal || hasCapability(data, permission);
  const hasRequiredGroup = !allowedGroups.length || allowedGroups.some((group) => groups.includes(group));
  const hasRequiredAttributeSet = hasRequiredAttributes(data?.attributes || {}, requiredAttributes);
  if (!hasBasePermission || !hasRequiredGroup || !hasRequiredAttributeSet) {
    return <Alert variant="danger">Vous n’avez pas la permission d’accéder à ce module.</Alert>;
  }
  return children;
};

PermissionGuard.propTypes = {
  type: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  permission: PropTypes.string,
  portal: PropTypes.oneOfType([
    PropTypes.oneOf(['learner', 'parent', 'staff']),
    PropTypes.arrayOf(PropTypes.oneOf(['learner', 'parent', 'staff'])),
  ]),
  allowedGroups: PropTypes.arrayOf(PropTypes.string),
  requiredAttributes: PropTypes.objectOf(PropTypes.oneOfType([
    PropTypes.string, PropTypes.number, PropTypes.bool, PropTypes.arrayOf(PropTypes.string),
  ])),
  children: PropTypes.node.isRequired,
};

export default PermissionGuard;
