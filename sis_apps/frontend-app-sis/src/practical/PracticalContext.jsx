import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import PropTypes from 'prop-types';
import { Alert, Button } from '@openedx/paragon';
import { useIsFetching, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchApi, postApi } from '../services/api';
import { resourceUrl } from '../services/resources';
import {
  checked, checkedCommand, errorMessage, evidencePath, isConflict, isDenied, multipart, queryOptions,
} from './practicalContract';

const PracticalContext = createContext(null);
export const usePractical = () => useContext(PracticalContext);
export const PracticalProvider = ({
  variant, scope, checking = false, children,
}) => {
  const client = useQueryClient();
  const [failure, setFailure] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const alive = useRef(true);
  const denied = useRef(false);
  const sending = useRef(false);
  const requests = useRef(new Set());
  const minimumVersions = useRef(new Map());
  const root = resourceUrl(variant, 'stages/pratique');
  const key = useMemo(() => ['practical', scope], [scope]);
  const capabilitiesFetching = useIsFetching({ queryKey: [...key, 'capacites/'], exact: true });
  const verifying = checking || capabilitiesFetching > 0;
  const accessChecking = useRef(verifying);
  accessChecking.current = verifying;
  const purge = useCallback(() => {
    requests.current.forEach(controller => controller.abort());
    minimumVersions.current.clear();
    client.cancelQueries({ queryKey: key });
    client.removeQueries({ queryKey: key });
  }, [client, key]);
  const deny = useCallback(error => {
    denied.current = true;
    if (alive.current) { setFailure(error); setNotice(''); setBusy(false); }
    purge();
  }, [purge]);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; purge(); };
  }, [purge]);
  const request = useCallback(async (path, schema, options = {}, payload = undefined) => {
    if (!alive.current || denied.current) { throw new Error('L’accès au suivi pratique a été retiré.'); }
    if (payload !== undefined && accessChecking.current) {
      throw new Error('Vérification des accès en cours. Aucune commande n’a été envoyée.');
    }
    if (!/^[a-z0-9][a-z0-9/_-]*(?:\?[^#]*)?$/.test(path) || path.includes('..')) {
      throw new Error('Route pratique invalide.');
    }
    const controller = new AbortController();
    requests.current.add(controller);
    const abort = () => controller.abort();
    options.signal?.addEventListener('abort', abort, { once: true });
    if (options.signal?.aborted) { controller.abort(); }
    try {
      const settings = { ...options, signal: controller.signal };
      const data = payload === undefined ? await fetchApi(`${root}${path}`, settings)
        : await postApi(`${root}${path}`, payload, settings);
      if (!alive.current || denied.current || controller.signal.aborted) {
        throw new Error('Contexte modifié : la réponse privée a été écartée.');
      }
      try {
        const result = schema ? checked(schema, data) : data;
        const aggregate = /^((?:dossiers|programmes)\/[1-9]\d*\/)/.exec(path)?.[1];
        if (['Dossier', 'Report', 'Programme'].includes(schema)
          && result.version < (minimumVersions.current.get(aggregate) || 0)) {
          throw new Error('La relecture est antérieure à la commande confirmée. Actualisez avant toute opération.');
        }
        return result;
      } catch (error) {
        if (payload !== undefined) { error.received = true; }
        throw error;
      }
    } catch (error) {
      if (isDenied(error)) { deny(error); }
      throw error;
    } finally {
      requests.current.delete(controller);
      options.signal?.removeEventListener('abort', abort);
    }
  }, [root, deny]);
  const refresh = useCallback(async () => {
    setNotice('');
    await client.invalidateQueries({ queryKey: key }, { throwOnError: true });
    if (denied.current || !alive.current) { throw new Error('Accès retiré pendant la relecture.'); }
  }, [client, key]);
  const command = useCallback(async ({
    path, schema, response, payload, file, maxBytes, dossierId, programmeId,
  }) => {
    if (sending.current) { throw new Error('Une opération est déjà en cours.'); }
    if (accessChecking.current) { throw new Error('Attendez la fin de la vérification des accès.'); }
    checkedCommand(schema, payload, variant);
    const body = multipart(payload, file, maxBytes);
    sending.current = true; setBusy(true); setNotice('');
    let received = false;
    try {
      const result = await request(path, response, {}, body);
      received = true;
      if (result.version !== payload.version + 1
        || (result.dossier && (result.dossier.version !== result.version
          || result.rapport.version !== result.version || result.rapport.dossier_id !== result.dossier.id))
        || (result.programme && result.programme.version !== result.version)
        || (dossierId && (
          result.dossier?.id || result.heure?.dossier_id || result.evaluation?.dossier_id
        ) !== dossierId)
        || (programmeId && result.programme?.id !== programmeId)) {
        throw new Error('La réponse ne confirme pas la version ou le dossier demandé.');
      }
      const aggregate = result.programme ? `programmes/${result.programme.id}/`
        : `dossiers/${result.dossier?.id || result.heure?.dossier_id || result.evaluation?.dossier_id}/`;
      minimumVersions.current.set(aggregate, result.version);
      await refresh();
      if (payload.version === 0) {
        await request(aggregate, result.programme ? 'Programme' : 'Dossier');
        if (result.dossier) { await request(`${aggregate}rapport/`, 'Report'); }
      }
      if (!alive.current || denied.current) { throw new Error('Accès retiré.'); }
      const released = result.heures_annulees?.length || 0;
      setNotice(`Opération confirmée et données relues.${released ? ` ${released} saisie(s) en attente annulée(s), conservée(s) dans l’historique.` : ''}`);
      return result;
    } catch (error) {
      if (isConflict(error)) {
        try { await refresh(); } catch (reloadError) {
          if (isDenied(reloadError)) { throw reloadError; }
          throw new Error(`Conflit. Relecture indisponible : ${errorMessage(reloadError)}. Aucune commande n’a été rejouée.`);
        }
      }
      if ((received || error.received) && !isDenied(error)) {
        const unconfirmed = new Error(`Une réponse a été reçue, mais la confirmation/relecture a échoué. Ne renvoyez pas la commande avant vérification. ${errorMessage(error)}`);
        unconfirmed.received = true;
        throw unconfirmed;
      }
      throw error;
    } finally {
      sending.current = false;
      if (alive.current) { setBusy(false); }
    }
  }, [request, refresh, variant]);
  const download = useCallback(async evidence => {
    if (accessChecking.current) { throw new Error('Attendez la fin de la vérification des accès.'); }
    if (!evidence.actions.can_download || !evidencePath(evidence.download_url)) {
      throw new Error('Téléchargement privé indisponible.');
    }
    const path = evidence.download_url.slice('/api/v1/stages/pratique/'.length);
    const blob = await request(path, null, { responseType: 'blob' });
    if (!alive.current || denied.current || accessChecking.current) {
      throw new Error('Accès retiré ou en cours de vérification : téléchargement abandonné.');
    }
    if (!(blob instanceof Blob) || !/^application\/pdf(?:;|$)/i.test(blob.type) || !blob.size) {
      throw new Error('Le serveur n’a pas renvoyé le PDF privé attendu.');
    }
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement('a');
      link.href = url; link.download = evidence.nom; link.click();
    } finally { URL.revokeObjectURL(url); }
  }, [request]);
  const context = useMemo(() => ({
    key,
    request,
    refresh,
    command,
    download,
    deny,
    variant,
    busy: busy || verifying,
    notice,
    clearNotice: () => setNotice(''),
  }), [key, request, refresh, command, download, deny, variant, busy, verifying, notice]);
  if (failure) {
    return <Alert variant="danger">Accès refusé ou retiré. Les données privées et les fichiers en mémoire ont été effacés. {errorMessage(failure)}</Alert>;
  }
  return (
    <PracticalContext.Provider value={context}>
      {verifying && <p role="status">Vérification des accès en cours. Les formulaires sont conservés et désactivés.</p>}
      <fieldset hidden={verifying} disabled={verifying} className="border-0 p-0 m-0 w-100">
        {children}
      </fieldset>
    </PracticalContext.Provider>
  );
};
PracticalProvider.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  scope: PropTypes.string.isRequired,
  checking: PropTypes.bool,
  children: PropTypes.node.isRequired,
};

export const usePracticalQuery = (path, schema, enabled = true) => {
  const { key, request } = usePractical();
  return useQuery({
    ...queryOptions,
    queryKey: [...key, path],
    queryFn: ({ signal }) => request(path, schema, { signal }),
    enabled,
  });
};

export const RefreshButton = () => {
  const { refresh, busy } = usePractical();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  return (
    <>
      <Button
        variant="outline-primary"
        disabled={busy || loading}
        onClick={async () => {
          setLoading(true); setError(null);
          try { await refresh(); } catch (failure) { setError(failure); } finally { setLoading(false); }
        }}
      >Actualiser le suivi pratique
      </Button>
      {error && <Alert variant="danger">{errorMessage(error)}</Alert>}
    </>
  );
};
