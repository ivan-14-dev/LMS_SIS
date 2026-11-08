import React from 'react';
import PropTypes from 'prop-types';
import { Stack, TextField, Typography } from '@mui/material';
import { dateFieldsType } from './eventUi';

const EventDates = ({
  start, end, onStart, onEnd, disabled, calendar,
}) => (
  <Stack spacing={2}>
    <Typography variant="body2">
      Horaires avec fuseau explicite : vérifiez le décalage UTC de chaque borne
      (France métropolitaine : +01:00 en hiver, +02:00 en été). Aucun changement automatique du décalage.
      {calendar ? ' Période positive de 93 jours maximum, fin exclue.' : ' Durée positive de 7 jours maximum.'}
    </Typography>
    {[{ name: 'Début', value: start, change: onStart }, { name: 'Fin', value: end, change: onEnd }].map(item => (
      <Stack key={item.name} direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField
          fullWidth
          label={`${item.name}${calendar ? ' de la période' : ' de l’événement'}`}
          type="datetime-local"
          required
          disabled={disabled}
          value={item.value.local}
          onChange={event => item.change({ ...item.value, local: event.target.value })}
          slotProps={{ inputLabel: { shrink: true }, htmlInput: { step: 1 } }}
        />
        <TextField
          label={`Décalage UTC — ${item.name.toLocaleLowerCase('fr')}`}
          required
          disabled={disabled}
          value={item.value.offset}
          onChange={event => item.change({ ...item.value, offset: event.target.value })}
          helperText="±HH:MM, par exemple +01:00"
          slotProps={{ htmlInput: { maxLength: 6, pattern: '[+-][0-9]{2}:[0-9]{2}' } }}
        />
      </Stack>
    ))}
  </Stack>
);
EventDates.propTypes = {
  start: dateFieldsType.isRequired, end: dateFieldsType.isRequired,
  onStart: PropTypes.func.isRequired, onEnd: PropTypes.func.isRequired,
  disabled: PropTypes.bool, calendar: PropTypes.bool,
};
export default EventDates;
