import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Button } from '@openedx/paragon';
import { useIsFetching, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { useCapabilities } from '../components/auth/PermissionGuard';
import { hasCapability } from '../components/layout/navigation';
import { fetchApi } from '../services/api';
import { resourceUrl } from '../services/resources';
import {
  PracticalProvider, RefreshButton, usePractical, usePracticalQuery,
} from './PracticalContext';
import { Collection, Failure, Field } from './PracticalControls';
import { CreateProgramme, ProgrammePanel } from './PracticalProgrammes';
import PracticalDossier from './PracticalDossier';
import {
  errorMessage, labelStatus, practicalPermissions, queryOptions,
} from './practicalContract';

const Workspace = () => {
  const {
    key, variant, busy, notice, clearNotice, deny,
  } = usePractical();
  const client = useQueryClient();
  const fetching = useIsFetching({ queryKey: key });
  const [parameters, setParameters] = useSearchParams();
  const [create, setCreate] = useState(false);
  const [status, setStatus] = useState('');
  const caps = usePracticalQuery('capacites/', 'Capabilities');
  const previous = useRef(null);
  const { data } = caps;
  const withdrawn = data && previous.current && (
    previous.current.permissions.some(permission => !data.permissions.includes(permission))
    || Object.keys(data.actions).some(action => previous.current.actions[action] && !data.actions[action])
  );
  useEffect(() => {
    if (data && !caps.isFetching) {
      if (withdrawn || data.variant !== variant) {
        deny(new Error('Le périmètre, la variante ou les habilitations pratiques ont changé. Rechargez la page pour revérifier l’accès.'));
      }
      previous.current = data;
    }
  }, [data, caps.isFetching, withdrawn, variant, deny]);
  const select = (kind, id) => {
    if (busy) { return; }
    const next = new URLSearchParams(parameters);
    next.delete('programme'); next.delete('dossier');
    if (id) { next.set(kind, String(id)); }
    setCreate(false); clearNotice(); setParameters(next);
  };
  const afterOpen = id => {
    const next = new URLSearchParams(parameters);
    next.delete('programme'); next.set('dossier', String(id)); setParameters(next);
  };
  const programmeId = parameters.get('programme');
  const dossierId = parameters.get('dossier');
  const selection = dossierId || programmeId;
  const validId = !selection || (/^[1-9]\d*$/.test(selection) && Number.isSafeInteger(Number(selection)));
  if (caps.error) { return <Failure error={caps.error} retry={() => caps.refetch()} />; }
  if (!data || withdrawn) { return <p role="status">Vérification des habilitations pratiques…</p>; }
  if (!data.permissions.length || !Object.values(data.actions).some(Boolean)) {
    return <Alert variant="warning">Aucun périmètre de suivi pratique n’est accessible avec vos habilitations actuelles.</Alert>;
  }
  const manage = data.permissions.includes('stages.gerer_suivi_pratique');
  const readError = client.getQueryCache().findAll({ queryKey: key }).some(query => query.state.error);
  return (
    <div>
      <h1>Stages pratiques</h1>
      <Alert variant="info">
        Suivi du travail réellement effectué et des compétences professionnelles.
        Ce bilan n’est ni une note officielle, ni un crédit académique, ni une décision de diplôme.
        Le suivi historique des conventions reste dans son espace séparé.
      </Alert>
      <p>Horloge institutionnelle : {data.fuseau_horaire} — {data.date_locale} {data.heure_locale}.</p>
      <div className="sis-practical-actions">
        <Button variant="outline-primary" disabled={busy} onClick={() => select(null, null)}>Programmes et dossiers autorisés</Button>
        <RefreshButton />
      </div>
      {notice && !fetching && !readError && <Alert variant="success">{notice}</Alert>}
      {!validId && <Alert variant="danger">Identifiant de sélection invalide. Revenez à la liste autorisée.</Alert>}
      {validId && dossierId && data.actions.can_list_dossiers && (
        <PracticalDossier key={dossierId} id={Number(dossierId)} capabilities={data} />
      )}
      {validId && !dossierId && programmeId && manage && data.actions.can_list_programmes && (
        <ProgrammePanel
          key={programmeId}
          id={Number(programmeId)}
          onOpened={afterOpen}
          canOpen={data.actions.can_open_dossier}
        />
      )}
      {!selection && (
        <>
          {manage && data.actions.can_create_programme && (
            <Button disabled={busy || caps.isFetching} onClick={() => { clearNotice(); setCreate(true); }}>
              Nouveau programme pratique
            </Button>
          )}
          {create && manage && data.actions.can_create_programme && (
            <CreateProgramme
              onClose={() => setCreate(false)}
              onCreated={id => {
                const next = new URLSearchParams(parameters);
                next.set('programme', String(id)); setParameters(next);
              }}
            />
          )}
          {manage && data.actions.can_list_programmes && (
            <Collection path="programmes/" schema="Programme" title="Programmes autorisés" empty="Aucun programme dans votre périmètre. Un gestionnaire habilité peut créer et publier les exigences d’un cursus admissible.">
              {rows => rows.map(item => (
                <p key={item.id}>
                  <Button variant="link" disabled={busy || caps.isFetching} onClick={() => select('programme', item.id)}>Ouvrir le programme {item.revision_courante.titre}</Button>
                  {' '}— {item.curriculum.libelle} — révision {item.revision_courante.numero} — {labelStatus(item.revision_courante.statut)}
                </p>
              ))}
            </Collection>
          )}
          {data.actions.can_list_dossiers && (
          <Collection
            key={status}
            path={`dossiers/${status ? `?statut=${status}` : ''}`}
            schema="Dossier"
            title="Dossiers autorisés"
            empty="Aucun dossier visible. L’ouverture exige un programme publié, une convention existante complète et une inscription éligible. Un gestionnaire habilité sélectionne ces prérequis ; cette page ne crée pas de convention."
            filters={(
              <Field
                label="État des dossiers"
                options={['ouvert', 'clos', 'annule'].map(value => [value, labelStatus(value)])}
                emptyOption="Tous les états"
                value={status}
                disabled={busy}
                onChange={setStatus}
              />
                )}
          >
            {rows => rows.map(item => (
              <p key={item.id}>
                <Button variant="link" disabled={busy || caps.isFetching} onClick={() => select('dossier', item.id)}>Ouvrir le dossier de {item.apprenant.utilisateur.nom} — {item.programme.titre}</Button>
                {' '}— {item.entreprise.nom} — {labelStatus(item.statut)}
              </p>
            ))}
          </Collection>
          )}
        </>
      )}
    </div>
  );
};

const PracticalTrainingPage = ({ variant }) => {
  const capabilities = useCapabilities(variant, { retry: false });
  const global = capabilities.data;
  const moduleEnabled = global?.modules?.['sis.practical_training'] === true;
  const namedAccess = Array.isArray(global?.permissions)
    && practicalPermissions.some(permission => hasCapability(global, permission));
  const profileUrl = resourceUrl(variant, 'utilisateurs/comptes');
  const profile = useQuery({
    ...queryOptions,
    queryKey: ['profile', profileUrl],
    queryFn: ({ signal }) => fetchApi(`${profileUrl}me/`, { signal }),
    enabled: moduleEnabled && namedAccess && !capabilities.error,
  });
  if (capabilities.error || profile.error) {
    return <Alert variant="danger">Impossible de vérifier l’accès au suivi pratique. Les données privées sont masquées. {errorMessage(capabilities.error || profile.error)}</Alert>;
  }
  if (!global || !capabilities.isFetchedAfterMount) { return <p role="status">Vérification du module pratique…</p>; }
  if (!moduleEnabled) { return <Alert variant="warning">Le module Stages pratiques est désactivé ou indisponible.</Alert>; }
  if (!namedAccess) { return <Alert variant="danger">Vous n’avez pas la permission d’accéder à ce module.</Alert>; }
  if (!profile.isFetchedAfterMount) { return <p role="status">Vérification du compte et de l’établissement…</p>; }
  if (!profile.data?.id || !profile.data?.etablissement) { return <Alert variant="danger">Compte ou établissement indisponible.</Alert>; }
  const scope = JSON.stringify([variant, profileUrl, profile.data.id, profile.data.etablissement, global]);
  return (
    <PracticalProvider
      key={scope}
      scope={scope}
      variant={variant}
      checking={capabilities.isFetching || profile.isFetching}
    >
      <Workspace />
    </PracticalProvider>
  );
};
PracticalTrainingPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default PracticalTrainingPage;
