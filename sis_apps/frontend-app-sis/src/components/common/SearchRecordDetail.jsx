import React from 'react';
import PropTypes from 'prop-types';
import { Link, useOutletContext, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Typography,
} from '@mui/material';
import PageHeader from './PageHeader';
import { academicSearchResources, usePrivateResource } from '../../services/academicSearch';
import { apiErrorMessage, resourceUrl } from '../../services/resources';

const definitions = {
  factures: {
    title: 'Facture',
    endpoint: 'paiements/factures',
    fields: [
      ['Numéro', 'numero'], ['Élève', 'eleve_nom'], ['Étudiant', 'etudiant_nom'],
      ['Rubrique', 'type_frais_libelle'], ['Statut', 'statut_display'],
      ['Montant', 'montant'], ['Montant payé', 'montant_paye'],
      ['Reste à payer', 'reste_a_payer'], ['Reste à payer', 'montant_restant'],
      ['Émission', 'date_emission'], ['Échéance', 'date_echeance'],
    ],
  },
  releves: {
    title: 'Relevé de notes',
    endpoint: 'releves',
    fields: [
      ['Série', 'numero_serie'], ['Étudiant', 'etudiant_nom'], ['Matricule', 'etudiant_matricule'],
      ['Semestre', 'semestre_nom'], ['Moyenne', 'moyenne_generale'],
      ['Crédits validés', 'credits_valides'], ['Date', 'date_emission'],
    ],
  },
  transcripts: {
    title: 'Transcript',
    endpoint: 'releves/transcripts',
    fields: [
      ['Série', 'numero_serie'], ['Étudiant', 'etudiant_nom'], ['Diplôme préparé', 'diplome_prepare'],
      ['Moyenne pondérée', 'moyenne_ponderee'], ['Crédits validés', 'credits_valides'], ['Date', 'date_emission'],
    ],
  },
  attestations: {
    title: 'Attestation',
    endpoint: 'releves/attestations',
    fields: [
      ['Numéro', 'numero'], ['Étudiant', 'etudiant_nom'], ['Type', 'type_display'],
      ['Émission', 'date_emission'], ['Validité', 'date_validite'],
    ],
  },
  parcours: {
    title: 'Parcours',
    endpoint: 'formations/parcours',
    fields: [['Code', 'code'], ['Nom', 'nom'], ['Description', 'description']],
  },
};

const Record = ({ variant, resource, id }) => {
  const definition = definitions[resource];
  const request = usePrivateResource(`${resourceUrl(variant, definition.endpoint)}${id}/`);
  if (request.loading) { return <Typography role="status">Chargement du dossier…</Typography>; }
  if (request.error) {
    return (
      <Alert severity="error" action={<Button onClick={request.retry}>Réessayer le dossier</Button>}>
        {request.error.response?.status === 403
          ? 'Accès refusé (403) : vous ne pouvez pas consulter ce dossier.'
          : `Impossible de charger ce dossier. ${apiErrorMessage(request.error)}`}
      </Alert>
    );
  }
  const record = request.data;
  if (!record || String(record.id) !== id) { return <Alert severity="error">Réponse de dossier invalide reçue du serveur.</Alert>; }
  return (
    <>
      <PageHeader title={definition.title} subtitle={record.numero || record.numero_serie || record.code} />
      <Box component="dl">
        {definition.fields.filter(([, field]) => record[field] != null).map(([label, field]) => (
          <Box key={field} sx={{ mb: 2 }}>
            <Typography component="dt" variant="subtitle2">{label}</Typography>
            <Typography component="dd" sx={{ m: 0 }}>{String(record[field])}</Typography>
          </Box>
        ))}
      </Box>
      {['releves', 'transcripts', 'attestations'].includes(resource) && (
        <Alert severity="info">
          La validation administrative n’est pas une signature numérique vérifiable.
          Les versions signées sont consultables dans l’espace documentaire.
        </Alert>
      )}
      <Button component={Link} to={`/${variant}`}>Retour à mon espace</Button>
    </>
  );
};
Record.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  resource: PropTypes.string.isRequired,
  id: PropTypes.string.isRequired,
};

const SearchRecordDetail = ({ resource }) => {
  const { id, documentType } = useParams();
  const { variant, capabilities, searchContext } = useOutletContext();
  const selected = resource || documentType;
  if (!searchContext) { return <Alert severity="info">Vérification de vos accès avant la consultation…</Alert>; }
  if (!definitions[selected] || !/^[1-9]\d*$/.test(id)
    || !academicSearchResources(variant, capabilities).some(item => item.value === selected)) {
    return <Alert severity="error">Vous n’avez pas accès à ce type de dossier dans ce contexte.</Alert>;
  }
  return <Record key={`${searchContext}:${selected}:${id}`} variant={variant} resource={selected} id={id} />;
};
SearchRecordDetail.propTypes = { resource: PropTypes.string };
SearchRecordDetail.defaultProps = { resource: undefined };
export default SearchRecordDetail;
