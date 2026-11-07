import PropTypes from 'prop-types';

export const candidateType = PropTypes.shape({
  id: PropTypes.number.isRequired,
  nom: PropTypes.string.isRequired,
});
export const projectType = PropTypes.shape({
  id: PropTypes.string.isRequired,
  titre: PropTypes.string.isRequired,
  description: PropTypes.string,
  mode: PropTypes.string.isRequired,
  version: PropTypes.number.isRequired,
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
export const limitations = 'Ces évaluations pédagogiques ne sont pas des notes officielles SIS. Aucun rattachement aux cours, classes, ECUE ou compétences, aucun transfert de notes ni synchronisation LMS n’est réalisé.';
