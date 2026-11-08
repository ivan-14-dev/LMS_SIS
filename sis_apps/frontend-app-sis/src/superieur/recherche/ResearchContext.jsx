import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import PropTypes from 'prop-types';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button } from '@openedx/paragon';
import { fetchApi, patchApi, postApi } from '../../services/api';
import { resourceUrl } from '../../services/resources';
import { errorMessage, isDenied } from './researchUi';

export const queryOptions = {
  retry: false, staleTime: 0, gcTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: true,
};
const ResearchContext = createContext(null);
export const useResearch = () => useContext(ResearchContext);

export const ResearchProvider = ({ scope, checking, children }) => {
  const client = useQueryClient();
  const [failure, setFailure] = useState(null);
  const [epoch, setEpoch] = useState(0);
  const [navigationBlocked, setNavigationBlocked] = useState(false);
  const alive = useRef(true);
  const locked = useRef(checking);
  locked.current = checking;
  const requests = useRef(new Set());
  const root = resourceUrl('superieur', 'recherche');
  const key = useMemo(() => ['research', scope, epoch], [scope, epoch]);
  const purge = useCallback(() => {
    requests.current.forEach(controller => controller.abort());
    client.cancelQueries({ queryKey: ['research', scope] });
    client.removeQueries({ queryKey: ['research', scope] });
  }, [client, scope]);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; purge(); };
  }, [purge]);
  const deny = useCallback(error => {
    if (alive.current) { setFailure(error); purge(); }
  }, [purge]);
  const request = useCallback(async (path, method = 'get', payload = undefined, options = {}) => {
    if (!alive.current || locked.current) { throw new Error('Vérification de la session en cours. Réessayez ensuite.'); }
    if (!/^[a-z0-9][a-z0-9/-]*(?:\?.*)?$/i.test(path) || path.includes('..')) {
      throw new Error('Route de recherche invalide.');
    }
    const controller = new AbortController();
    requests.current.add(controller);
    const abort = () => controller.abort();
    options.signal?.addEventListener('abort', abort, { once: true });
    try {
      const settings = { ...options, signal: controller.signal };
      const result = await (method === 'get' ? fetchApi(`${root}${path}`, settings)
        : (method === 'patch' ? patchApi : postApi)(`${root}${path}`, payload, settings));
      if (!alive.current || controller.signal.aborted || locked.current) {
        throw new Error('Le contexte de session a changé. La réponse a été écartée.');
      }
      return result;
    } catch (error) {
      if (isDenied(error)) { deny(error); }
      throw error;
    } finally {
      options.signal?.removeEventListener('abort', abort);
      requests.current.delete(controller);
    }
  }, [root, deny]);
  const refresh = useCallback(async () => {
    await client.invalidateQueries({ queryKey: key }, { throwOnError: true });
  }, [client, key]);
  const download = useCallback(async (path, filename, kind) => {
    const blob = await request(path, 'get', undefined, { responseType: 'blob' });
    const types = {
      pdf: /^application\/pdf(?:;|$)/i,
      csv: /^(text\/csv|application\/(csv|octet-stream))(?:;|$)/i,
      proof: /^(application\/pdf|image\/(png|jpeg))(?:;|$)/i,
    };
    if (!(blob instanceof Blob) || !types[kind]?.test(blob.type)) {
      throw new Error('Le serveur n’a pas renvoyé le fichier privé attendu.');
    }
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement('a');
      link.href = url; link.download = filename; link.click();
    } finally {
      URL.revokeObjectURL(url);
    }
  }, [request]);
  const context = useMemo(() => ({
    key, request, refresh, download, checking, deny, navigationBlocked, setNavigationBlocked,
  }), [key, request, refresh, download, checking, deny, navigationBlocked]);
  if (failure) {
    return (
      <Alert variant="danger">
        {errorMessage(failure)}
        <Button onClick={() => { setEpoch(value => value + 1); setFailure(null); }}>Revérifier les accès</Button>
      </Alert>
    );
  }
  return <ResearchContext.Provider value={context}>{children}</ResearchContext.Provider>;
};
ResearchProvider.propTypes = {
  scope: PropTypes.string.isRequired, checking: PropTypes.bool, children: PropTypes.node.isRequired,
};

export const useResearchQuery = (path, enabled = true) => {
  const { key, request, checking } = useResearch();
  return useQuery({
    ...queryOptions,
    queryKey: [...key, path],
    queryFn: ({ signal }) => request(path, 'get', undefined, { signal }),
    enabled: Boolean(enabled && path && !checking),
  });
};

export const paginated = data => {
  if (!data || !Array.isArray(data.results) || !Number.isSafeInteger(data.count) || data.count < 0) {
    throw new Error('Le serveur n’a pas fourni la collection paginée attendue.');
  }
  return data;
};

export const useLeaveGuard = enabled => {
  const { setNavigationBlocked } = useResearch();
  useEffect(() => {
    setNavigationBlocked(enabled);
    const preventLeaving = event => {
      event.preventDefault();
      // Older browsers require returnValue for the native leave-page confirmation.
      // eslint-disable-next-line no-param-reassign
      event.returnValue = '';
    };
    if (enabled) { window.addEventListener('beforeunload', preventLeaving); }
    return () => {
      setNavigationBlocked(false);
      window.removeEventListener('beforeunload', preventLeaving);
    };
  }, [enabled, setNavigationBlocked]);
};
