import PropTypes from 'prop-types';
import { dateLabel } from '../projects/projectUi';

export const queryOptions = {
  retry: false, gcTime: 0, staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: 'always',
};
export const isDenied = error => [401, 403, 404].includes(error?.response?.status);
export const eventAccess = data => Boolean(data?.can_create || data?.can_manage || data?.can_consult);
export const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const accountType = PropTypes.shape({ id: PropTypes.number.isRequired, nom: PropTypes.string.isRequired });
export const roomType = PropTypes.shape({
  id: PropTypes.number.isRequired,
  code: PropTypes.string,
  nom: PropTypes.string.isRequired,
  capacite: PropTypes.number.isRequired,
});
export const eventType = PropTypes.shape({
  id: PropTypes.string.isRequired,
  titre: PropTypes.string.isRequired,
  description: PropTypes.string,
  type: PropTypes.string.isRequired,
  statut: PropTypes.string.isRequired,
  debut: PropTypes.string.isRequired,
  fin: PropTypes.string.isRequired,
  salle: roomType.isRequired,
  effectif: PropTypes.number.isRequired,
  version: PropTypes.number.isRequired,
  can_manage: PropTypes.bool.isRequired,
  participants: PropTypes.arrayOf(accountType),
});
export const choiceType = PropTypes.shape({ value: PropTypes.string.isRequired, label: PropTypes.string.isRequired });
export const roomLabel = room => `${room.code || ''} — ${room.nom} · capacité ${room.capacite}`;
export const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'local';
export const choiceLabel = (choices, value) => choices.find(item => item.value === value)?.label || value;

const pad = value => String(value).padStart(2, '0');
export const dateFields = value => {
  const date = new Date(value);
  const offset = -date.getTimezoneOffset();
  return {
    local: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`,
    offset: `${offset < 0 ? '-' : '+'}${pad(Math.floor(Math.abs(offset) / 60))}:${pad(Math.abs(offset) % 60)}`,
  };
};
export const dateFieldsType = PropTypes.shape({
  local: PropTypes.string.isRequired, offset: PropTypes.string.isRequired,
});
export const eventDateLabel = value => `${dateLabel(value)} (${timeZone}, UTC${dateFields(value).offset})`;

// Keep the offset explicit: a daylight-saving transition must not silently move an entered time.
export const isoDate = ({ local, offset }) => {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(local)
      || !/^[+-](0\d|1[0-4]):[0-5]\d$/.test(offset)
      || (offset.slice(1, 3) === '14' && offset.slice(4) !== '00')) {
    throw new Error('Indiquez une date et un décalage UTC explicite valide, par exemple +01:00.');
  }
  const seconds = local.length === 16 ? `${local}:00` : local;
  const wallTime = new Date(`${seconds}Z`);
  if (!Number.isFinite(wallTime.getTime()) || wallTime.toISOString().slice(0, 19) !== seconds) {
    throw new Error('La date ou l’heure saisie est invalide.');
  }
  const result = `${seconds}${offset}`;
  if (!Number.isFinite(new Date(result).getTime())) { throw new Error('La date saisie est invalide.'); }
  return result;
};
export const intervalPayload = (start, end, days) => {
  const debut = isoDate(start);
  const fin = isoDate(end);
  const duration = new Date(fin) - new Date(debut);
  if (duration <= 0 || duration > days * 86400000) {
    throw new Error(`L’intervalle doit être positif et limité à ${days} jours.`);
  }
  return { debut, fin };
};
export const initialInterval = () => {
  const now = new Date();
  return {
    start: dateFields(new Date(now.getFullYear(), now.getMonth(), 1)),
    end: dateFields(new Date(now.getFullYear(), now.getMonth() + 1, 1)),
  };
};
export const checkedCapabilities = data => {
  if (!data || !['can_create', 'can_manage', 'can_consult'].every(key => typeof data[key] === 'boolean')
      || !['types', 'statuts'].every(key => Array.isArray(data[key])
        && data[key].every(choice => typeof choice.value === 'string' && typeof choice.label === 'string'))
      || data.notifications !== 'internes') {
    throw new Error('Réponse de capacités événementielles invalide.');
  }
  return data;
};
export const checkedEvent = (data, id, detail = true) => {
  if (!uuidPattern.test(data?.id) || (id && data.id !== id)
      || !Number.isInteger(data.version) || data.version < 1
      || !['planifie', 'annule'].includes(data.statut) || typeof data.can_manage !== 'boolean'
      || typeof data.titre !== 'string' || typeof data.description !== 'string'
      || !['conference', 'examen', 'reunion', 'ceremonie', 'activite'].includes(data.type)
      || !Number.isInteger(data.effectif) || data.effectif < 1
      || !Number.isInteger(data.salle?.id) || typeof data.salle.nom !== 'string'
      || !Number.isInteger(data.salle.capacite)
      || ![data.debut, data.fin].every(value => typeof value === 'string'
        && /(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(new Date(value).getTime()))
      || (detail && data.can_manage && (!Array.isArray(data.participants)
        || !data.participants.every(person => Number.isInteger(person.id) && typeof person.nom === 'string')))) {
    throw new Error('Réponse événement invalide. Rechargez l’agenda avant toute nouvelle opération.');
  }
  const { participants, ...safe } = data;
  return detail && data.can_manage ? { ...safe, participants } : safe;
};
