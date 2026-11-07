import PropTypes from 'prop-types';

export const candidateType = PropTypes.shape({
  id: PropTypes.number.isRequired,
  nom: PropTypes.string.isRequired,
});
export const courseType = PropTypes.shape({
  id: PropTypes.number,
  nom: PropTypes.string,
  disponible: PropTypes.bool,
  contexte: PropTypes.shape({
    classe: candidateType,
    matiere: candidateType,
    ecue: candidateType,
  }),
});
export const courseLabel = course => {
  const context = course.contexte;
  return context?.ecue
    ? `${course.nom} · ECUE ${context.ecue.code} — ${context.ecue.nom}`
    : `${course.nom} · ${context?.classe?.nom || ''} / ${context?.matiere?.nom || ''}`;
};
export const bindingLabel = course => {
  if (!course) { return 'Aucun cours rattaché.'; }
  return course.disponible
    ? `Cours rattaché : ${courseLabel(course)}`
    : 'Rattachement conservé — cours indisponible dans votre périmètre actuel.';
};
export const criterionType = PropTypes.shape({
  code: PropTypes.string.isRequired, label: PropTypes.string.isRequired,
});
export const competencyType = PropTypes.shape({
  disponible: PropTypes.bool, version: PropTypes.number, criteria: PropTypes.arrayOf(criterionType),
});
export const competencyLabel = snapshot => {
  if (!snapshot) { return 'Aucune compétence visée sélectionnée.'; }
  return snapshot.disponible
    ? `Compétences visées : ${snapshot.criteria.map(item => `${item.label} (${item.code})`).join(', ')}`
    : 'Compétences visées conservées — indisponibles dans votre périmètre actuel.';
};
export const projectType = PropTypes.shape({
  id: PropTypes.string.isRequired,
  titre: PropTypes.string.isRequired,
  description: PropTypes.string,
  mode: PropTypes.string.isRequired,
  version: PropTypes.number.isRequired,
  responsable: PropTypes.number,
  cours: courseType,
  competences: competencyType,
  actions: PropTypes.shape({
    can_manage: PropTypes.bool, can_submit: PropTypes.bool, can_evaluate: PropTypes.bool,
  }).isRequired,
});
export const teamType = PropTypes.shape({
  id: PropTypes.string.isRequired,
  nom: PropTypes.string.isRequired,
  membres: PropTypes.arrayOf(PropTypes.shape({
    membre: PropTypes.number.isRequired, nom: PropTypes.string.isRequired,
  })).isRequired,
  actions: PropTypes.shape({
    can_manage: PropTypes.bool, can_submit: PropTypes.bool, can_evaluate: PropTypes.bool,
  }).isRequired,
});
export const milestoneType = PropTypes.shape({
  id: PropTypes.string.isRequired,
  titre: PropTypes.string.isRequired,
  bareme: PropTypes.string.isRequired,
});
export const queryOptions = {
  retry: false, gcTime: 0, staleTime: 0, refetchOnMount: 'always',
};
export const isDenied = error => [401, 403, 404].includes(error?.response?.status);
export const dateLabel = value => new Date(value).toLocaleString('fr');
export const selectProps = { select: { native: true }, inputLabel: { shrink: true } };
export const rules = 'Un apprenant appartient à une seule équipe active par projet. En mode individuel, chaque équipe est créée avec une personne et reste limitée à une personne active. Une équipe vide conserve ses preuves, sans dépôt ni publication.';
export const limitations = 'Rattachement facultatif à un cours existant et à son contexte classe/matière ou ECUE, sans créer de cours ni accorder d’accès. Un mapping local ne prouve pas le provisioning LMS. Ces évaluations ne sont pas des notes officielles SIS : compétences, résultats officiels, transfert de notes et synchronisation LMS restent distincts.';
