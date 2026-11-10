import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Button } from '@openedx/paragon';
import {
  Collection, CommandForm, Download, Field, recordType,
} from './ResearchControls';
import { useResearch } from './ResearchContext';
import { MetadataEditor } from './ResearchEditors';
import ResearchFinance from './ResearchFinance';
import {
  multipart, pdfFile, statusLabel, validDate,
} from './researchUi';

const Milestones = ({ project }) => {
  const [command, setCommand] = useState(null);
  const { refresh, checking } = useResearch();
  const path = `projets-recherche/${project.id}/`;
  const canCreate = project.can_manage && !project.archive
    && ['propose', 'accepte', 'en_cours'].includes(project.statut) && project.can_add_jalon !== false;
  const canSubmit = project.can_contribute && !project.archive && project.statut === 'en_cours';
  const canAccept = project.can_manage && !project.archive && project.statut === 'en_cours'
    && project.can_valider_jalon !== false;
  const commandAllowed = command && ((command.action === 'jalons' && canCreate)
    || (command.action === 'livrables' && canSubmit) || (command.action === 'valider-jalon' && canAccept));
  const title = {
    jalons: 'Créer un jalon', livrables: 'Déposer une révision PDF', 'valider-jalon': 'Accepter le jalon',
  }[command?.action];
  return (
    <section aria-label="Jalons et livrables" className="my-4">
      {canCreate && <Button disabled={checking || Boolean(command)} onClick={() => setCommand({ action: 'jalons' })}>Nouveau jalon</Button>}
      {commandAllowed && (
        <CommandForm
          key={`${command.action}-${command.milestone?.id || ''}`}
          title={title}
          path={`${path}${command.action}/`}
          recordPath={path}
          record={project}
          contributor={command.action === 'livrables'}
          onSaved={refresh}
          onClose={() => setCommand(null)}
          build={(values, version) => {
            if (command.action === 'jalons') {
              const date = validDate(values.echeance);
              if (date < project.date_debut || date > project.date_fin) { throw new Error('L’échéance doit être comprise dans la période du projet.'); }
              return {
                version, titre: values.titre, description: values.description || '', echeance: date,
              };
            }
            const payload = { version, jalon: command.milestone.id };
            return command.action === 'livrables' ? multipart({
              ...payload, fichier: pdfFile(values.fichier), commentaire: values.commentaire || '',
            }) : payload;
          }}
        >
          {(values, change) => (
            <>
              {command.milestone && <p>Jalon : {command.milestone.titre}</p>}
              {command.action === 'jalons' && (
                <>
                  <Field label="Titre du jalon" value={values.titre} onChange={value => change('titre', value)} maxLength={300} required />
                  <Field label="Description du jalon" type="textarea" value={values.description} onChange={value => change('description', value)} />
                  <Field label="Échéance du jalon" type="date" min={project.date_debut} max={project.date_fin} value={values.echeance} onChange={value => change('echeance', value)} required />
                  <p>La définition du jalon est immuable après création.</p>
                </>
              )}
              {command.action === 'livrables' && (
                <>
                  <Field label="Livrable PDF" type="file" accept=".pdf,application/pdf" onChange={value => change('fichier', value)} required />
                  {values.fichier && <p>{values.fichier.name}</p>}
                  <Field label="Commentaire de la révision" type="textarea" value={values.commentaire} onChange={value => change('commentaire', value)} />
                  <p>
                    Un nouveau numéro de révision sera attribué par le serveur.
                    Les précédents dépôts restent immuables.
                  </p>
                </>
              )}
              {command.action === 'valider-jalon' && <p>Après acceptation, aucun dépôt ne pourra remplacer les travaux acceptés.</p>}
            </>
          )}
        </CommandForm>
      )}
      <Collection resource={`${path}jalons`} title="Jalons et livrables" searchable={false}>
        {rows => rows.map(milestone => (
          <article key={milestone.id} className="sis-panel mb-3">
            <h3>{milestone.titre}</h3>
            <p>{milestone.description}</p>
            <p>Échéance : {milestone.echeance} — {statusLabel(milestone.statut)}</p>
            {canSubmit && milestone.statut !== 'accepte' && (
              <Button disabled={checking || Boolean(command)} onClick={() => setCommand({ action: 'livrables', milestone })}>Déposer pour {milestone.titre}</Button>
            )}
            {canAccept && milestone.statut === 'soumis' && (
              <Button className="ml-2" disabled={checking || Boolean(command)} onClick={() => setCommand({ action: 'valider-jalon', milestone })}>Valider {milestone.titre}</Button>
            )}
            {!milestone.livrables?.length && <p>Aucune révision déposée.</p>}
            {(milestone.livrables || []).map(delivery => (
              <div key={delivery.id} className="border-top my-3 pt-3">
                <h4>Révision {delivery.revision} — {delivery.nom}</h4>
                <p>{delivery.created_at} — {delivery.taille} octets</p>
                <p>{delivery.commentaire}</p>
                <p>SHA-256 : <code>{delivery.sha256}</code></p>
                <Download path={`${path}livrables/${delivery.id}/fichier/`} filename={delivery.nom}>Télécharger la révision {delivery.revision}</Download>
              </div>
            ))}
          </article>
        ))}
      </Collection>
    </section>
  );
};
Milestones.propTypes = { project: recordType.isRequired };

const ResearchProject = ({ project, onSelect }) => {
  const [create, setCreate] = useState(null);
  const { navigationBlocked } = useResearch();
  return (
    <>
      {project.can_read_academic === true && (
        <>
          <section aria-label="Équipe et description">
            <h2>Équipe et recherche</h2>
            <p>{project.description}</p>
            <p>Responsable : {project.responsable_nom}</p>
            <p>Membres chercheurs : {(project.membres_list || []).map(item => item.nom).join(', ') || 'Aucun autre chercheur.'}</p>
          </section>
          <Milestones project={project} />
          {project.can_manage && !project.archive && !navigationBlocked && (
            <div className="my-3">
              <Button disabled={Boolean(create)} onClick={() => setCreate('theses')}>Nouvelle thèse liée</Button>
              <Button disabled={Boolean(create)} className="ml-2" onClick={() => setCreate('productions-scientifiques')}>Nouvelle publication liée</Button>
            </div>
          )}
          {create && project.can_manage && !project.archive && (
            <MetadataEditor resource={create} project={project} onClose={() => setCreate(null)} />
          )}
          <Collection resource="productions-scientifiques" title="Publications du projet" filter={`&projet=${project.id}`} onSelect={id => onSelect('productions-scientifiques', id)} />
          <Collection resource="theses" title="Encadrements accessibles du projet" filter={`&projet=${project.id}`} onSelect={id => onSelect('theses', id)} />
        </>
      )}
      {project.can_read_academic !== true && <Alert variant="info">Vue financière limitée. Aucun dossier doctoral, publication privée ou livrable académique n’est chargé.</Alert>}
      {project.can_finance === true && <ResearchFinance project={project} />}
    </>
  );
};
ResearchProject.propTypes = { project: recordType.isRequired, onSelect: PropTypes.func.isRequired };
export default ResearchProject;
