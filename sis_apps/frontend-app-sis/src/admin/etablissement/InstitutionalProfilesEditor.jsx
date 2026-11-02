import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Checkbox, FormControlLabel, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { postApi } from '../../services/api';
import { apiErrorMessage } from '../../services/resources';

const clone = value => JSON.parse(JSON.stringify(value));
const nextCode = (prefix, items) => {
  const codes = new Set(items.map(item => item.code));
  let index = 1;
  while (codes.has(`${prefix}-${index}`)) { index += 1; }
  return `${prefix}-${index}`;
};
const optionShape = PropTypes.shape({ code: PropTypes.string, label: PropTypes.string });
const assessmentShape = PropTypes.shape({
  mode: PropTypes.string,
  minimum: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  maximum: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  pass_mark: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  criteria: PropTypes.arrayOf(optionShape),
});
const offeringShape = PropTypes.shape({
  code: PropTypes.string,
  label: PropTypes.string,
  profile: PropTypes.string,
  version: PropTypes.number,
  calendar: PropTypes.string,
  terminology: PropTypes.shape({
    learner: PropTypes.string, educator: PropTypes.string, group: PropTypes.string,
  }),
  assessment: assessmentShape,
  credits: PropTypes.shape({
    system: PropTypes.string,
    target: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  }),
});
const schemaShape = PropTypes.shape({
  profiles: PropTypes.arrayOf(PropTypes.shape({
    code: PropTypes.string, label: PropTypes.string, template: offeringShape,
  })),
  calendars: PropTypes.arrayOf(optionShape),
  assessment_modes: PropTypes.arrayOf(optionShape),
  assessment_templates: PropTypes.shape({
    numeric: assessmentShape,
    competency: assessmentShape,
    pass_fail: assessmentShape,
  }),
});
const numericInput = value => ['number', 'string'].includes(typeof value);
const editable = offer => offer && typeof offer.code === 'string'
  && typeof offer.label === 'string' && typeof offer.profile === 'string'
  && typeof offer.calendar === 'string' && Number.isInteger(offer.version)
  && ['learner', 'educator', 'group'].every(key => typeof offer.terminology?.[key] === 'string')
  && ['numeric', 'competency', 'pass_fail'].includes(offer.assessment?.mode)
  && (offer.assessment.mode !== 'numeric'
    || ['minimum', 'maximum', 'pass_mark'].every(key => numericInput(offer.assessment[key])))
  && (offer.assessment.mode !== 'competency' || (
    Array.isArray(offer.assessment.criteria)
    && offer.assessment.criteria.every(item => typeof item?.code === 'string' && typeof item?.label === 'string')
  ))
  && (offer.credits === null || (
    offer.credits && typeof offer.credits.system === 'string' && numericInput(offer.credits.target)
  ));

const OfferingEditor = ({
  offer, schema, onChange, onRemove, endpoint,
}) => {
  const [trial, setTrial] = useState({});
  const preview = useMutation({ mutationFn: payload => postApi(`${endpoint}offering-preview/`, payload) });
  const { assessment } = offer;
  const criteria = assessment.criteria || [];
  const criterionResult = code => (Object.prototype.hasOwnProperty.call(trial, code) ? trial[code] : null);
  let result;
  if (assessment.mode === 'numeric') {
    result = { score: trial.score === undefined || trial.score === '' ? null : trial.score };
  } else if (assessment.mode === 'competency') {
    result = { criteria: Object.fromEntries(criteria.map(item => [item.code, criterionResult(item.code)])) };
  } else {
    result = { passed: trial.passed ?? null };
  }
  const payload = { offering: offer, result };
  const currentPreview = JSON.stringify(preview.variables) === JSON.stringify(payload);
  const update = changes => {
    setTrial({});
    onChange({ ...offer, ...changes });
  };
  const updateAssessment = changes => update({ assessment: { ...assessment, ...changes } });
  const choice = (label, value, options, onChangeValue) => (
    <TextField select label={label} value={value} onChange={event => onChangeValue(event.target.value)} fullWidth>
      {options.map(option => <MenuItem key={option.code} value={option.code}>{option.label}</MenuItem>)}
    </TextField>
  );
  const decisionOptions = [
    { code: '', label: 'Non renseigné' }, { code: 'yes', label: 'Acquis / validé' },
    { code: 'no', label: 'Non acquis / non validé' },
  ];
  const decisionValue = value => {
    if (value === undefined || value === null) { return ''; }
    return value ? 'yes' : 'no';
  };
  const parseDecision = value => (value === '' ? null : value === 'yes');
  return (
    <Box component="section" aria-label={offer.label || offer.code} sx={{ border: 1, borderColor: 'divider', p: 2 }}>
      <Stack spacing={2}>
        <Typography component="h2" variant="h6">{offer.label || offer.code}</Typography>
        <Typography variant="body2">
          Code : {offer.code} · Profil :{' '}
          {schema.profiles.find(item => item.code === offer.profile)?.label || offer.profile}
          {' '}· Version : {offer.version}
        </Typography>
        <TextField label="Nom de l’offre" value={offer.label} onChange={event => update({ label: event.target.value })} required />
        {choice('Calendrier', offer.calendar, schema.calendars, calendar => update({ calendar }))}
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
          {Object.entries({ learner: 'Apprenant', educator: 'Enseignant / formateur', group: 'Classe / groupe' }).map(([key, label]) => (
            <TextField
              key={key}
              label={`Libellé ${label}`}
              value={offer.terminology[key]}
              onChange={event => update({ terminology: { ...offer.terminology, [key]: event.target.value } })}
              required
              fullWidth
            />
          ))}
        </Stack>
        {choice('Mode d’évaluation', assessment.mode, schema.assessment_modes, mode => update({
          assessment: clone(schema.assessment_templates[mode]),
        }))}
        <Typography variant="body2">Changer de mode reprend ses règles par défaut.</Typography>
        {assessment.mode === 'numeric' && (
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            {Object.entries({ minimum: 'Note minimale', maximum: 'Note maximale', pass_mark: 'Seuil de réussite' }).map(([key, label]) => (
              <TextField
                key={key}
                label={label}
                type="number"
                slotProps={{ htmlInput: { step: 'any' } }}
                value={assessment[key] ?? ''}
                onChange={event => updateAssessment({ [key]: event.target.value })}
                required
                fullWidth
              />
            ))}
          </Stack>
        )}
        {assessment.mode === 'competency' && (
          <Stack spacing={2}>
            {criteria.map(item => (
              <Stack direction="row" spacing={1} key={item.code}>
                <TextField
                  label={`Compétence ${item.code}`}
                  value={item.label}
                  onChange={event => updateAssessment({
                    criteria: criteria.map(current => (
                      current.code === item.code ? { ...current, label: event.target.value } : current
                    )),
                  })}
                  required
                  fullWidth
                />
                <Button
                  type="button"
                  aria-label={`Retirer ${item.label}`}
                  onClick={() => updateAssessment({
                    criteria: criteria.filter(current => current.code !== item.code),
                  })}
                >Retirer
                </Button>
              </Stack>
            ))}
            <Button
              type="button"
              onClick={() => updateAssessment({
                criteria: [...criteria, { code: nextCode('competence', criteria), label: 'Nouvelle compétence' }],
              })}
            >Ajouter une compétence
            </Button>
          </Stack>
        )}
        <FormControlLabel
          label="Utiliser des crédits"
          control={(
            <Checkbox
              checked={offer.credits !== null}
              onChange={event => update({ credits: event.target.checked ? { system: 'Crédits locaux', target: 1 } : null })}
            />
          )}
        />
        {offer.credits !== null && (
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <TextField label="Système de crédits" value={offer.credits.system} onChange={event => update({ credits: { ...offer.credits, system: event.target.value } })} required />
            <TextField label="Crédits visés" type="number" slotProps={{ htmlInput: { step: 'any' } }} value={offer.credits.target ?? ''} onChange={event => update({ credits: { ...offer.credits, target: event.target.value } })} required />
          </Stack>
        )}
        <Typography component="h3" variant="subtitle1">Simuler les règles</Typography>
        {assessment.mode === 'numeric' && (
          <TextField label="Note à simuler" type="number" slotProps={{ htmlInput: { step: 'any' } }} value={trial.score ?? ''} onChange={event => setTrial({ score: event.target.value })} />
        )}
        {assessment.mode === 'competency' && criteria.map(item => (
          <React.Fragment key={item.code}>
            {choice(`Résultat : ${item.label}`, decisionValue(criterionResult(item.code)), decisionOptions, value => setTrial({ ...trial, [item.code]: parseDecision(value) }))}
          </React.Fragment>
        ))}
        {assessment.mode === 'pass_fail' && choice('Décision à simuler', decisionValue(trial.passed), decisionOptions, value => setTrial({ passed: parseDecision(value) }))}
        <Button type="button" disabled={preview.isPending} onClick={() => preview.mutate(payload)}>Simuler</Button>
        {currentPreview && preview.isError && <Alert severity="error">{apiErrorMessage(preview.error)}</Alert>}
        {currentPreview && preview.isSuccess && (
          <Alert severity={preview.data.status === 'passed' ? 'success' : 'info'}>
            {preview.data.detail} Simulation uniquement : aucune note, décision ou attribution de crédits enregistrée.
          </Alert>
        )}
        <Button type="button" color="error" onClick={onRemove}>Retirer cette configuration d’offre</Button>
      </Stack>
    </Box>
  );
};

OfferingEditor.propTypes = {
  offer: offeringShape.isRequired,
  schema: schemaShape.isRequired,
  onChange: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
  endpoint: PropTypes.string.isRequired,
};

const InstitutionalProfilesEditor = ({
  value, schema, onChange, endpoint,
}) => {
  const [selected, setSelected] = useState('');
  if (!schema?.profiles?.length) {
    return <Alert severity="warning">Le catalogue de profils n’est pas disponible sur ce serveur.</Alert>;
  }
  if (!Array.isArray(value) || !value.every(editable)
    || new Set(value.map(offer => offer.code)).size !== value.length) {
    return <Alert severity="error">La structure des offres est invalide. Corrigez la configuration JSON avant de poursuivre.</Alert>;
  }
  const template = schema.profiles.find(profile => profile.code === selected);
  const addOffering = () => {
    const offer = clone(template.template);
    onChange([...value, { ...offer, code: nextCode(template.code, value) }]);
  };
  return (
    <Stack spacing={3} sx={{ my: 3 }}>
      <Alert severity="info">
        Combinez plusieurs offres dans le même établissement. Ces configurations ne modifient pas
        les classes, formations, notes ou crédits existants. Leur raccordement aux parcours métier
        reste distinct. Les modules pédagogiques se règlent dans l’onglet Modules.
      </Alert>
      <TextField select label="Profil à ajouter" value={selected} onChange={event => setSelected(event.target.value)}>
        <MenuItem value="">Choisir un profil</MenuItem>
        {schema.profiles.map(profile => <MenuItem key={profile.code} value={profile.code}>{profile.label}</MenuItem>)}
      </TextField>
      <Button type="button" disabled={!template} onClick={addOffering}>Ajouter une offre</Button>
      {value.length === 0 && <Typography>Aucune offre configurée. Le fonctionnement existant est conservé.</Typography>}
      {value.map(offer => (
        <OfferingEditor
          key={offer.code}
          offer={offer}
          schema={schema}
          endpoint={endpoint}
          onChange={updated => onChange(value.map(current => (current.code === offer.code ? updated : current)))}
          onRemove={() => onChange(value.filter(current => current.code !== offer.code))}
        />
      ))}
      <Typography variant="body2">Utilisez « Enregistrer la configuration » pour conserver les offres de cet établissement.</Typography>
    </Stack>
  );
};

InstitutionalProfilesEditor.propTypes = {
  value: PropTypes.arrayOf(offeringShape).isRequired,
  schema: schemaShape.isRequired,
  onChange: PropTypes.func.isRequired,
  endpoint: PropTypes.string.isRequired,
};

export default InstitutionalProfilesEditor;
