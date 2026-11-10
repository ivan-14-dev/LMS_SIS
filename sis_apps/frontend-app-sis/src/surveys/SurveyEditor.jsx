import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Checkbox, FormControlLabel, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import CollectionPagination from '../components/common/CollectionPagination';
import { apiErrorMessage, fetchResourcePage } from '../services/resources';

const SurveyEditor = ({
  url, survey, busy, onSave, onCancel,
}) => {
  const [title, setTitle] = useState(survey?.titre || '');
  const [description, setDescription] = useState(survey?.description || '');
  const [questions, setQuestions] = useState(survey?.questionnaire || [{
    id: 'q1', libelle: '', type: 'texte', choix: [],
  }]);
  const [recipients, setRecipients] = useState(survey?.destinataires || []);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const candidates = useQuery({
    queryKey: ['surveys', url, 'candidates', search, page],
    queryFn: ({ signal }) => fetchResourcePage(`${url}candidats/`, { q: search.trim(), page, page_size: 20 }, { signal }),
    enabled: search.trim().length >= 2 && !busy,
    retry: false,
    gcTime: 0,
  });
  const updateQuestion = (index, values) => setQuestions(current => current.map(
    (question, position) => (position === index ? { ...question, ...values } : question),
  ));
  const submit = event => {
    event.preventDefault();
    onSave({
      titre: title,
      description,
      politique: 'nominative',
      questionnaire: questions,
      destinataires: recipients.map(item => item.id),
      ...(survey ? { version: survey.version } : {}),
    });
  };
  if (candidates.error && [401, 403].includes(candidates.error.response?.status)) {
    return <Alert severity="error">Sélection interdite. {apiErrorMessage(candidates.error)}<Button onClick={onCancel}>Retour</Button></Alert>;
  }
  return (
    <Stack component="form" onSubmit={submit} spacing={2} aria-label="Configurer une enquête">
      <Typography variant="h2">{survey ? 'Modifier le brouillon' : 'Nouvelle enquête nominative'}</Typography>
      <TextField label="Titre" value={title} onChange={event => setTitle(event.target.value)} required disabled={busy} inputProps={{ maxLength: 200 }} />
      <TextField label="Description" value={description} onChange={event => setDescription(event.target.value)} disabled={busy} multiline inputProps={{ maxLength: 3000 }} />
      <Typography>Toutes les questions sont obligatoires. 20 questions maximum ; 200 destinataires maximum.</Typography>
      {questions.map((question, index) => (
        <Stack key={question.id} spacing={1} component="fieldset" className="sis-fieldset" disabled={busy}>
          <Typography component="legend">Question {index + 1}</Typography>
          <TextField label={`Question ${index + 1}`} value={question.libelle} onChange={event => updateQuestion(index, { libelle: event.target.value })} required inputProps={{ maxLength: 300 }} />
          <TextField
            select
            label={`Type de question ${index + 1}`}
            value={question.type}
            onChange={event => updateQuestion(index, { type: event.target.value, choix: [] })}
          >
            <MenuItem value="texte">Texte libre (2 000 caractères)</MenuItem>
            <MenuItem value="choix">Choix unique</MenuItem>
          </TextField>
          {question.type === 'choix' && (
            <TextField
              label={`Choix de la question ${index + 1}`}
              helperText="Un choix par ligne, de 2 à 10 choix distincts (120 caractères chacun)."
              multiline
              required
              value={question.choix.join('\n')}
              onChange={event => updateQuestion(index, { choix: event.target.value.split('\n') })}
            />
          )}
          <Button
            disabled={busy || questions.length === 1}
            onClick={() => setQuestions(current => current.filter((_, position) => position !== index))}
          >Retirer la question {index + 1}
          </Button>
        </Stack>
      ))}
      <Button
        disabled={busy || questions.length >= 20}
        onClick={() => {
          let index = 1;
          const used = new Set(questions.map(question => question.id));
          while (used.has(`q${index}`)) { index += 1; }
          setQuestions(current => [...current, {
            id: `q${index}`, libelle: '', type: 'texte', choix: [],
          }]);
        }}
      >Ajouter une question
      </Button>
      <Typography variant="h3">Destinataires sélectionnés ({recipients.length}/200)</Typography>
      {recipients.map(item => (
        <FormControlLabel
          key={item.id}
          label={`${item.nom} · ${item.profil}`}
          control={(
            <Checkbox
              checked
              disabled={busy}
              onChange={() => setRecipients(current => current.filter(value => value.id !== item.id))}
            />
          )}
        />
      ))}
      <TextField
        label="Rechercher un destinataire"
        helperText="Comptes actifs de cet établissement, tous profils existants. Au moins 2 caractères."
        value={search}
        disabled={busy}
        inputProps={{ maxLength: 100 }}
        onChange={event => { setSearch(event.target.value); setPage(1); }}
      />
      {candidates.error && <Alert severity="error">{apiErrorMessage(candidates.error)}</Alert>}
      {search.trim().length >= 2 && !candidates.error && (
        candidates.isFetching ? <Typography>Recherche…</Typography> : (
          <>
            {(candidates.data?.results || []).map(item => (
              <Button
                key={item.id}
                disabled={busy || recipients.length >= 200 || recipients.some(value => value.id === item.id)}
                onClick={() => setRecipients(current => [...current, item])}
              >Ajouter {item.nom} · {item.profil}
              </Button>
            ))}
            {!candidates.data?.count && <Typography>Aucun compte trouvé.</Typography>}
            <CollectionPagination
              data={candidates.data}
              page={page}
              setPage={setPage}
              disabled={busy}
              label="Destinataires"
              previousLabel="Candidats précédents"
              nextLabel="Candidats suivants"
            />
          </>
        )
      )}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
        <Button type="submit" variant="contained" disabled={busy || !recipients.length}>Enregistrer le brouillon</Button>
        <Button disabled={busy} onClick={onCancel}>Annuler</Button>
      </Stack>
    </Stack>
  );
};
SurveyEditor.propTypes = {
  url: PropTypes.string.isRequired,
  survey: PropTypes.shape({
    titre: PropTypes.string,
    description: PropTypes.string,
    questionnaire: PropTypes.arrayOf(PropTypes.shape({})),
    destinataires: PropTypes.arrayOf(PropTypes.shape({})),
    version: PropTypes.number,
  }),
  busy: PropTypes.bool.isRequired,
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};
export default SurveyEditor;
