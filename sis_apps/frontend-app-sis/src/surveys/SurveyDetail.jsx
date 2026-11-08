import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Checkbox, FormControlLabel, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import SurveyEditor from './SurveyEditor';

const SurveyDetail = ({
  url, survey, results, managing, busy, onCommand,
}) => {
  const [editing, setEditing] = useState(false);
  const [answers, setAnswers] = useState({});
  const [consent, setConsent] = useState(false);
  if (editing) {
    return (
      <SurveyEditor
        url={url}
        survey={survey}
        busy={busy}
        onCancel={() => setEditing(false)}
        onSave={async payload => {
          await onCommand('configurer/', payload);
          setEditing(false);
        }}
      />
    );
  }
  const ownResponse = survey.ma_reponse;
  return (
    <Stack spacing={2}>
      <Typography variant="h2">{survey.titre}</Typography>
      <Typography>{survey.description}</Typography>
      <Typography>Statut : {survey.statut}</Typography>
      {managing ? (
        <>
          <Stack direction="row" spacing={1}>
            {survey.statut === 'brouillon' && (
              <>
                <Button disabled={busy} onClick={() => setEditing(true)}>Modifier le brouillon</Button>
                <Button disabled={busy} onClick={() => onCommand('publier/', { version: survey.version })}>Publier dans les portails</Button>
              </>
            )}
            {survey.statut === 'publiee' && <Button disabled={busy} onClick={() => onCommand('fermer/', { version: survey.version })}>Fermer l’enquête</Button>}
          </Stack>
          {survey.statut === 'brouillon' && <Alert severity="info">La publication fige les questions et la sélection. Les accès restent révocables.</Alert>}
          <Typography variant="h3">Questionnaire</Typography>
          {survey.questionnaire.map(question => (
            <Typography key={question.id}>{question.libelle}{question.type === 'choix' ? ` : ${question.choix.join(' / ')}` : ' (texte libre)'}</Typography>
          ))}
          <Typography variant="h3">Destinataires</Typography>
          {survey.destinataires.map(item => (
            <Stack key={item.id} direction="row" spacing={1}>
              <Typography>{item.nom} · {item.profil}{item.revoked_at ? ' · Accès révoqué' : ''}</Typography>
              {survey.statut !== 'brouillon' && !item.revoked_at && (
                <Button disabled={busy} onClick={() => onCommand('revoquer/', { version: survey.version, destinataire: item.id })}>Révoquer {item.nom}</Button>
              )}
            </Stack>
          ))}
          {results && (
            <>
              <Typography variant="h3">Résultats nominatifs</Typography>
              <Typography>
                {results.reponses_recues} réponse(s) / {results.destinataires} destinataire(s).
                Les réponses déjà reçues restent conservées après révocation.
              </Typography>
              {results.choix.map(question => (
                <Stack key={question.id}>
                  <Typography>{question.libelle}</Typography>
                  {question.comptages.map(item => (
                    <Typography key={item.choix}>{item.choix} : {item.total}</Typography>
                  ))}
                </Stack>
              ))}
              {results.reponses.map(row => (
                <Stack key={row.destinataire.id} component="section" spacing={1}>
                  <Typography variant="h4">{row.destinataire.nom}{row.revoked_at ? ' · Accès révoqué' : ''}</Typography>
                  {survey.questionnaire.map(question => (
                    <Typography key={question.id}>{question.libelle} : {row.reponses[question.id]}</Typography>
                  ))}
                </Stack>
              ))}
            </>
          )}
        </>
      ) : (
        <Stack
          component="form"
          spacing={2}
          onSubmit={event => { event.preventDefault(); onCommand('repondre/', { politique: 'nominative', reponses: answers }); }}
        >
          {ownResponse && <Alert severity="success">Votre réponse a été enregistrée. Elle ne peut pas être remplacée.</Alert>}
          {!survey.peut_repondre && !ownResponse && <Alert severity="info">Cette enquête est fermée.</Alert>}
          {survey.questionnaire.map(question => (
            ownResponse || !survey.peut_repondre ? (
              <Typography key={question.id}>{question.libelle} : {ownResponse?.reponses[question.id] || 'Aucune réponse'}</Typography>
            ) : (
              <TextField
                key={question.id}
                label={question.libelle}
                value={answers[question.id] || ''}
                onChange={event => setAnswers(current => ({ ...current, [question.id]: event.target.value }))}
                select={question.type === 'choix'}
                multiline={question.type === 'texte'}
                inputProps={{ maxLength: 2000 }}
                required
                disabled={busy}
              >
                {question.type === 'choix' ? question.choix.map(option => (
                  <MenuItem key={option} value={option}>{option}</MenuItem>
                )) : null}
              </TextField>
            )
          ))}
          {survey.peut_repondre && (
            <>
              <FormControlLabel
                label="Je comprends que ma réponse est nominative et définitive."
                control={(
                  <Checkbox checked={consent} disabled={busy} onChange={event => setConsent(event.target.checked)} />
                )}
              />
              <Button type="submit" variant="contained" disabled={busy || !consent}>Envoyer ma réponse</Button>
            </>
          )}
        </Stack>
      )}
    </Stack>
  );
};
SurveyDetail.propTypes = {
  url: PropTypes.string.isRequired,
  survey: PropTypes.shape({
    titre: PropTypes.string.isRequired,
    description: PropTypes.string,
    statut: PropTypes.string.isRequired,
    version: PropTypes.number,
    questionnaire: PropTypes.arrayOf(PropTypes.shape({})).isRequired,
    destinataires: PropTypes.arrayOf(PropTypes.shape({})),
    ma_reponse: PropTypes.shape({ reponses: PropTypes.objectOf(PropTypes.string) }),
    peut_repondre: PropTypes.bool,
  }).isRequired,
  results: PropTypes.shape({
    reponses_recues: PropTypes.number,
    destinataires: PropTypes.number,
    choix: PropTypes.arrayOf(PropTypes.shape({})),
    reponses: PropTypes.arrayOf(PropTypes.shape({})),
  }),
  managing: PropTypes.bool.isRequired,
  busy: PropTypes.bool.isRequired,
  onCommand: PropTypes.func.isRequired,
};
export default SurveyDetail;
