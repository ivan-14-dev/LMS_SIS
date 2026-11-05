const admissionActions = (variant) => {
  const school = variant === 'secondaire';
  const pending = school ? 'en_cours' : 'provisoire';
  const reason = {
    name: 'motif', label: 'Justification', required: true, multiline: true,
  };
  return [
    { label: 'Valider', endpoint: 'valider', statuses: [pending] },
    {
      label: 'Refuser', endpoint: 'refuser', statuses: [pending], fields: [reason],
    },
    {
      label: 'Annuler la demande', endpoint: 'annuler', statuses: [pending], fields: [reason],
    },
    {
      label: 'Réinscrire / changer de cursus',
      endpoint: 'reinscrire',
      statuses: ['validee'],
      fields: [
        {
          name: school ? 'annee_scolaire' : 'annee_universitaire',
          label: 'Nouvelle année',
          resource: 'etablissement/annees',
          labelField: 'libelle',
          required: true,
        },
        {
          name: school ? 'classe' : 'formation',
          label: school ? 'Nouvelle classe' : 'Nouvelle formation',
          resource: school ? 'classes/classes' : 'formations/formations',
          required: true,
        },
        ...(!school ? [{ name: 'parcours', label: 'Nouveau parcours (facultatif)', resource: 'formations/parcours' }] : []),
        {
          name: 'date_inscription', label: 'Date de la nouvelle demande', type: 'date', required: true,
        },
        reason,
      ],
    },
  ];
};

export default admissionActions;
