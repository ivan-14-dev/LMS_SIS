import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button } from '@openedx/paragon';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { canAccessModule } from '../../components/layout/navigation';
import PageHeader from '../../components/common/PageHeader';
import { fetchApi } from '../../services/api';
import { resourceUrl } from '../../services/resources';
import {
  queryOptions, ResearchProvider, useResearch, useResearchQuery,
} from './ResearchContext';
import { Collection, Download, Failure } from './ResearchControls';
import { LifecycleCommand, MetadataEditor } from './ResearchEditors';
import ResearchProject from './ResearchProject';
import { commandsFor, resources, statusLabel } from './researchUi';

const researchModule = {
  module: 'sis.research',
  permission: 'recherche.gerer_recherche',
  alternatePermissions: [
    'recherche.consulter_recherche', 'recherche.contribuer_recherche', 'recherche.comptabiliser_recherche',
  ],
};

const RecordDetail = ({ resource, id, onSelect }) => {
  const query = useResearchQuery(`${resource}/${id}/`);
  const { checking, navigationBlocked } = useResearch();
  const [editor, setEditor] = useState(null);
  const row = query.data;
  if (query.error) { return <Failure error={query.error} retry={() => query.refetch()} />; }
  if (!row) { return <p role="status">Chargement du dossier…</p>; }
  const editable = row.can_manage === true && !row.archive
    && (resource !== 'productions-scientifiques' || row.statut === 'brouillon');
  const transitions = commandsFor(resource, row);
  const fields = {
    laboratoires: [
      ['faculte_nom', 'Faculté'], ['directeur_nom', 'Directeur'], ['numero_rnsr', 'Numéro RNSR'],
      ['tutelle', 'Tutelles'], ['axes_recherche', 'Axes de recherche'],
    ],
    'projets-recherche': [
      ['laboratoire_nom', 'Laboratoire'], ['financeur', 'Financeur'],
      ['reference', 'Référence'], ['budget', 'Budget (EUR)'], ['date_debut', 'Début'], ['date_fin', 'Fin'],
    ],
    theses: [
      ['projet_titre', 'Projet'], ['laboratoire_nom', 'Laboratoire'], ['doctorant_nom', 'Doctorant'],
      ['directeur_nom', 'Directeur'], ['co_directeur_nom', 'Co-directeur'], ['resume', 'Résumé'],
      ['mots_cles', 'Mots-clés'], ['date_debut', 'Début'], ['date_soutenance', 'Soutenance'], ['financement', 'Financement'],
    ],
    'productions-scientifiques': [
      ['projet_titre', 'Projet'], ['laboratoire_nom', 'Laboratoire'], ['type_display', 'Type'],
      ['annee', 'Année'], ['doi', 'DOI'], ['url_hal', 'URL HAL'], ['facteur_impact', 'Facteur d’impact'],
    ],
  };
  return (
    <section aria-label="Dossier de recherche">
      <h2>{row.titre || row.nom}</h2>
      <p>{row.acronyme} — {row.archive ? 'Archivé' : (row.statut_display || statusLabel(row.statut))} — Version {row.version}</p>
      {query.isFetching && <p role="status">Relecture de l’état serveur…</p>}
      <dl>
        {fields[resource].filter(([key]) => row[key] !== undefined && row[key] !== null).map(([key, label]) => (
          <React.Fragment key={key}><dt>{label}</dt><dd>{Array.isArray(row[key]) ? row[key].join(', ') : String(row[key]) || '—'}</dd></React.Fragment>
        ))}
      </dl>
      {resource === 'productions-scientifiques' && (
        <>
          <p>Auteurs : {(row.auteurs_list || []).map(item => item.nom).join(', ')}</p>
          {row.fichier ? <Download path={`${resource}/${id}/fichier/`} filename={`${row.titre}.pdf`}>Télécharger le PDF privé</Download> : <p>Aucun PDF joint.</p>}
        </>
      )}
      {editable && <Button disabled={Boolean(editor) || checking || query.isFetching || navigationBlocked} onClick={() => setEditor({ action: 'edit' })}>Modifier les métadonnées</Button>}
      {transitions.map(([action, title]) => (
        <Button
          className="ml-2"
          key={action}
          variant="outline-primary"
          disabled={Boolean(editor) || checking || query.isFetching || navigationBlocked}
          onClick={() => setEditor({ action, title })}
        >{title}
        </Button>
      ))}
      {resource === 'laboratoires' && row.can_manage && row.can_archiver === false && <p>Archivage possible après archivage de tous les projets du laboratoire.</p>}
      {resource === 'projets-recherche' && row.can_manage && row.statut === 'en_cours' && row.can_terminer === false && <p>Fin du projet indisponible : vérifiez l’acceptation des jalons et les engagements ouverts.</p>}
      {editor?.action === 'edit' && editable && <MetadataEditor resource={resource} record={row} onClose={() => setEditor(null)} />}
      {editor && editor.action !== 'edit' && transitions.some(([action]) => action === editor.action) && (
        <LifecycleCommand
          resource={resource}
          record={row}
          action={editor.action}
          title={editor.title}
          onClose={() => setEditor(null)}
        />
      )}
      {resource === 'projets-recherche' && <ResearchProject project={row} onSelect={onSelect} />}
    </section>
  );
};
RecordDetail.propTypes = {
  resource: PropTypes.string.isRequired,
  id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  onSelect: PropTypes.func.isRequired,
};

const ResearchWorkspace = () => {
  const capabilities = useResearchQuery('projets-recherche/capacites/');
  const { checking, navigationBlocked } = useResearch();
  const [selection, setSelection] = useState({ resource: 'projets-recherche', id: null });
  const [creating, setCreating] = useState(false);
  if (capabilities.error) { return <Failure error={capabilities.error} retry={() => capabilities.refetch()} />; }
  if (!capabilities.data) { return <p role="status">Vérification des capacités de recherche…</p>; }
  const caps = capabilities.data;
  const fields = ['can_create_laboratoire', 'can_create_projet', 'can_manage', 'can_contribute', 'can_finance'];
  if (fields.some(field => typeof caps[field] !== 'boolean')) {
    return <Alert variant="danger">Réponse de capacités incompatible : accès aux collections non ouvert.</Alert>;
  }
  const tabs = caps.can_manage ? Object.keys(resources) : ['projets-recherche'];
  const resource = tabs.includes(selection.resource) || selection.id ? selection.resource : 'projets-recherche';
  const select = (kind, id = null) => {
    if (navigationBlocked) { return; }
    setCreating(false); setSelection({ resource: kind, id });
  };
  const canCreate = (resource === 'laboratoires' && caps.can_create_laboratoire)
    || (resource === 'projets-recherche' && caps.can_create_projet)
    || (['theses', 'productions-scientifiques'].includes(resource) && caps.can_manage);
  return (
    <div>
      <PageHeader title="Recherche" subtitle="Dossiers, contributions et opérations autorisés dans votre établissement" />
      <nav aria-label="Domaines de recherche" className="d-flex flex-wrap mb-3">
        {tabs.map(kind => (
          <Button className="mr-2 mb-2" key={kind} variant={resource === kind ? 'primary' : 'outline-primary'} disabled={navigationBlocked || checking} onClick={() => select(kind)}>{resources[kind]}</Button>
        ))}
      </nav>
      {navigationBlocked && <Alert variant="warning">Terminez la vérification ou le rejeu de l’opération financière avant de changer de dossier.</Alert>}
      {selection.id ? (
        <>
          <Button variant="tertiary" disabled={navigationBlocked || checking} onClick={() => select(resource)}>Retour à la liste</Button>
          <RecordDetail key={`${resource}-${selection.id}`} resource={resource} id={selection.id} onSelect={select} />
        </>
      ) : (
        <>
          {canCreate && (
            <Button disabled={creating || checking} onClick={() => setCreating(true)}>
              Créer — {resources[resource]}
            </Button>
          )}
          {creating && canCreate && (
            <MetadataEditor key={`editor-${resource}`} resource={resource} onClose={() => setCreating(false)} />
          )}
          <Collection
            key={`collection-${resource}`}
            resource={resource}
            title={resources[resource]}
            onSelect={id => select(resource, id)}
          />
        </>
      )}
    </div>
  );
};

const RecherchePage = () => {
  const capabilities = useCapabilities('superieur', { retry: false });
  const allowed = canAccessModule(researchModule, capabilities.data);
  const profileUrl = resourceUrl('superieur', 'utilisateurs/comptes');
  const profile = useQuery({
    ...queryOptions,
    queryKey: ['profile', profileUrl],
    queryFn: ({ signal }) => fetchApi(`${profileUrl}me/`, { signal }),
    enabled: allowed && capabilities.isFetchedAfterMount && !capabilities.error && !capabilities.isFetching,
  });
  if (capabilities.error) {
    return (
      <Failure
        error={capabilities.error}
        retry={() => capabilities.refetch()}
      />
    );
  }
  if (!capabilities.isFetchedAfterMount || !capabilities.data) { return <p role="status">Vérification du module Recherche…</p>; }
  if (capabilities.data.modules?.['sis.research'] !== true) { return <Alert variant="warning">Le module Recherche est désactivé ou indisponible.</Alert>; }
  if (!allowed) { return <Alert variant="danger">Vous n’avez pas la permission d’accéder à ce module.</Alert>; }
  if (profile.error) { return <Failure error={profile.error} retry={() => profile.refetch()} />; }
  if (!profile.isFetchedAfterMount) { return <p role="status">Vérification du compte local et de l’établissement…</p>; }
  if (!profile.data?.id || !profile.data?.etablissement) { return <Alert variant="danger">Compte local ou établissement non vérifiable. Aucun dossier n’est affiché.</Alert>; }
  const scope = JSON.stringify([profileUrl, profile.data.id, profile.data.etablissement, capabilities.data]);
  const checking = capabilities.isFetching || profile.isFetching;
  return (
    <>
      {checking && <p role="status">Revérification de la session ; dossiers temporairement masqués…</p>}
      <div hidden={checking}>
        <ResearchProvider key={scope} scope={scope} checking={checking}>
          <ResearchWorkspace />
        </ResearchProvider>
      </div>
    </>
  );
};
export default RecherchePage;
