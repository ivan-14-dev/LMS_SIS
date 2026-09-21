import { getConfig } from '@edx/frontend-platform';
import { getAuthenticatedHttpClient } from '@edx/frontend-platform/auth';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  mockFetch, mockPost, mockPut, mockDelete, isMockMode,
} from './mockApi';

/**
 * Get the base URL for SIS Supérieur API
 */
export const getSuperieurApiUrl = () => {
  try {
    return getConfig().SIS_SUPERIEUR_API_URL || 'http://localhost:8002/api/v1';
  } catch {
    return 'http://localhost:8002/api/v1';
  }
};

/**
 * Get the base URL for SIS Secondaire API
 */
export const getSecondaireApiUrl = () => {
  try {
    return getConfig().SIS_SECONDAIRE_API_URL || 'http://localhost:8001/api/v1';
  } catch {
    return 'http://localhost:8001/api/v1';
  }
};

/**
 * Generic API fetch function
 */
export const fetchApi = async (url, options = {}) => {
  // Use mock data in development mode
  if (isMockMode()) {
    return mockFetch(url);
  }

  const client = getAuthenticatedHttpClient();
  const response = await client.get(url, options);
  return response.data;
};

/**
 * Generic API post function
 */
export const postApi = async (url, data, options = {}) => {
  if (isMockMode()) {
    return mockPost(url, data);
  }

  const client = getAuthenticatedHttpClient();
  const response = await client.post(url, data, options);
  return response.data;
};

/**
 * Generic API put function
 */
export const putApi = async (url, data, options = {}) => {
  if (isMockMode()) {
    return mockPut(url, data);
  }

  const client = getAuthenticatedHttpClient();
  const response = await client.put(url, data, options);
  return response.data;
};

/**
 * Generic API patch function
 */
export const patchApi = async (url, data, options = {}) => {
  if (isMockMode()) {
    return mockPut(url, data);
  }

  const client = getAuthenticatedHttpClient();
  const response = await client.patch(url, data, options);
  return response.data;
};

/**
 * Generic API delete function
 */
export const deleteApi = async (url, options = {}) => {
  if (isMockMode()) {
    return mockDelete(url);
  }

  const client = getAuthenticatedHttpClient();
  const response = await client.delete(url, options);
  return response.data;
};

const getVariantApiUrl = (apiType = 'superieur') => (apiType === 'secondaire' ? getSecondaireApiUrl() : getSuperieurApiUrl());

export const useWorkflowNotifications = (apiType = 'superieur', onlyUnread = true, params = {}) => useQuery({
  queryKey: ['workflow-notifications', apiType, onlyUnread, params],
  queryFn: () => {
    const query = new URLSearchParams({
      ...(onlyUnread ? { non_lues: '1' } : {}),
      ...Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')),
    }).toString();
    return fetchApi(`${getVariantApiUrl(apiType)}/core/notifications/${query ? `?${query}` : ''}`);
  },
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});

export const useWorkflowNotificationSummary = (apiType = 'superieur', params = {}) => useQuery({
  queryKey: ['workflow-notification-summary', apiType, params],
  queryFn: () => {
    const query = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')),
    ).toString();
    return fetchApi(`${getVariantApiUrl(apiType)}/core/notifications/bilan_livraison/${query ? `?${query}` : ''}`);
  },
});

export const useMarkAllWorkflowNotificationsRead = (apiType = 'superieur') => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => postApi(`${getVariantApiUrl(apiType)}/core/notifications/tout_marquer_lu/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow-notifications', apiType] });
    },
  });
};

export const useWorkflowHistory = (apiType = 'superieur', endpoint = '', enabled = true) => useQuery({
  queryKey: ['workflow-history', apiType, endpoint],
  queryFn: () => fetchApi(`${getVariantApiUrl(apiType)}/${endpoint}`),
  enabled: enabled && Boolean(endpoint),
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});

export const useWorkflowEvents = (apiType = 'superieur', params = {}) => useQuery({
  queryKey: ['workflow-events', apiType, params],
  queryFn: () => {
    const queryString = new URLSearchParams(params).toString();
    const suffix = queryString ? `?${queryString}` : '';
    return fetchApi(`${getVariantApiUrl(apiType)}/core/workflow-events/${suffix}`);
  },
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});

/**
 * Factory function to create CRUD hooks for a resource
 * @param {string} resourceName - Name of the resource (e.g., 'etudiants')
 * @param {string} apiType - 'superieur' or 'secondaire'
 */
export const createResourceHooks = (resourceName, apiType = 'superieur') => {
  const getBaseUrl = () => {
    const baseUrl = apiType === 'superieur' ? getSuperieurApiUrl() : getSecondaireApiUrl();
    return `${baseUrl}/${resourceName}`;
  };

  return {
    // List hook - normalizes paginated and non-paginated responses to array
    useList: (params = {}) => {
      const queryString = new URLSearchParams(params).toString();
      const url = queryString ? `${getBaseUrl()}/?${queryString}` : `${getBaseUrl()}/`;

      return useQuery({
        queryKey: [resourceName, 'list', params],
        queryFn: () => fetchApi(url),
        select: (data) => {
          // Handle paginated response { results: [...] } or direct array
          if (Array.isArray(data)) { return data; }
          if (data?.results && Array.isArray(data.results)) { return data.results; }
          return [];
        },
      });
    },

    // Detail hook
    useDetail: (id, enabled = true) => useQuery({
      queryKey: [resourceName, 'detail', id],
      queryFn: () => fetchApi(`${getBaseUrl()}/${id}/`),
      enabled: enabled && !!id,
    }),

    // Create hook
    useCreate: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: (data) => postApi(`${getBaseUrl()}/`, data),
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: [resourceName] });
        },
      });
    },

    // Update hook
    useUpdate: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: ({ id, data }) => putApi(`${getBaseUrl()}/${id}/`, data),
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: [resourceName] });
        },
      });
    },

    // Partial update hook
    usePatch: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: ({ id, data }) => patchApi(`${getBaseUrl()}/${id}/`, data),
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: [resourceName] });
        },
      });
    },

    // Delete hook
    useDelete: () => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: (id) => deleteApi(`${getBaseUrl()}/${id}/`),
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: [resourceName] });
        },
      });
    },

    // Custom action hook
    useAction: (actionName, method = 'post') => {
      const queryClient = useQueryClient();
      return useMutation({
        mutationFn: ({ id, data }) => {
          const url = `${getBaseUrl()}/${id}/${actionName}/`;
          switch (method) {
            case 'get':
              return fetchApi(url);
            case 'post':
              return postApi(url, data);
            case 'put':
              return putApi(url, data);
            case 'patch':
              return patchApi(url, data);
            case 'delete':
              return deleteApi(url);
            default:
              return postApi(url, data);
          }
        },
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: [resourceName] });
        },
      });
    },
  };
};

// ============ SIS SUPÉRIEUR HOOKS ============

// Étudiants
export const etudiantHooks = createResourceHooks('etudiants', 'superieur');
export const useEtudiants = etudiantHooks.useList;
export const useEtudiant = etudiantHooks.useDetail;
export const useCreateEtudiant = etudiantHooks.useCreate;
export const useUpdateEtudiant = etudiantHooks.useUpdate;
export const useDeleteEtudiant = etudiantHooks.useDelete;

// Formations
export const formationHooks = createResourceHooks('formations', 'superieur');
export const useFormations = () => useQuery({
  queryKey: ['formations', 'list'],
  queryFn: () => fetchApi(`${getSuperieurApiUrl()}/formations/formations/`),
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});
export const useFormation = (id, enabled = true) => useQuery({
  queryKey: ['formations', 'detail', id],
  queryFn: () => fetchApi(`${getSuperieurApiUrl()}/formations/formations/${id}/`),
  enabled: enabled && !!id,
});

// Inscriptions
export const inscriptionHooks = createResourceHooks('inscriptions', 'superieur');
export const useInscriptions = inscriptionHooks.useList;
export const useInscription = inscriptionHooks.useDetail;

// Notes
export const noteHooks = createResourceHooks('notes', 'superieur');
export const useNotes = (params = {}) => useQuery({
  queryKey: ['notes', 'list', params],
  queryFn: () => {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${getSuperieurApiUrl()}/notes/notes/?${queryString}` : `${getSuperieurApiUrl()}/notes/notes/`;
    return fetchApi(url);
  },
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});

// Examens
export const examenHooks = createResourceHooks('examens/epreuves', 'superieur');
export const useExamens = examenHooks.useList;
export const useExamen = examenHooks.useDetail;

// Bourses
export const typeBourseHooks = createResourceHooks('types-bourses', 'superieur');
export const demandeBourseHooks = createResourceHooks('demandes-bourses', 'superieur');
export const attributionBourseHooks = createResourceHooks('attributions-bourses', 'superieur');
export const useTypesBourses = typeBourseHooks.useList;
export const useDemandesBourses = demandeBourseHooks.useList;
export const useDemandeBourse = demandeBourseHooks.useDetail;
export const useCreateDemandeBourse = demandeBourseHooks.useCreate;

// Emploi du temps
export const creneauCoursHooks = createResourceHooks('creneaux-cours', 'superieur');
export const salleHooks = createResourceHooks('salles', 'superieur');
export const reservationHooks = createResourceHooks('reservations', 'superieur');
export const useCreneauxCours = creneauCoursHooks.useList;
export const useSalles = salleHooks.useList;
export const useReservations = reservationHooks.useList;

// Enseignants
export const enseignantHooks = createResourceHooks('enseignants', 'superieur');
export const useEnseignants = enseignantHooks.useList;
export const useEnseignant = enseignantHooks.useDetail;

// Stages
export const stageHooks = createResourceHooks('stages', 'superieur');
export const useStages = stageHooks.useList;

// Mémoires
export const memoireHooks = createResourceHooks('memoires', 'superieur');
export const useMemoires = memoireHooks.useList;

// Recherche
export const labHooks = createResourceHooks('laboratoires', 'superieur');
export const projetRechercheHooks = createResourceHooks('projets-recherche', 'superieur');
export const useLaboratoires = labHooks.useList;
export const useProjetsRecherche = projetRechercheHooks.useList;

// Diplômes
export const diplomeHooks = createResourceHooks('diplomes', 'superieur');
export const useDiplomes = diplomeHooks.useList;

// Paiements
export const paiementHooks = createResourceHooks('paiements', 'superieur');
export const usePaiements = () => useQuery({
  queryKey: ['paiements', 'list'],
  queryFn: () => fetchApi(`${getSuperieurApiUrl()}/paiements/transactions/`),
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});

// Jurys
export const juryHooks = createResourceHooks('jurys', 'superieur');
export const useJurys = juryHooks.useList;

// Relevés
export const releveHooks = createResourceHooks('releves', 'superieur');
export const useReleves = releveHooks.useList;

// Mobilité
export const mobiliteHooks = createResourceHooks('mobilites', 'superieur');
export const useMobilites = mobiliteHooks.useList;

// Bibliothèque
export const empruntHooks = createResourceHooks('emprunts', 'superieur');
export const useEmprunts = empruntHooks.useList;

// ============ SIS SECONDAIRE HOOKS ============

// Élèves
export const eleveHooks = createResourceHooks('eleves', 'secondaire');
export const useEleves = eleveHooks.useList;
export const useEleve = eleveHooks.useDetail;
export const useCreateEleve = eleveHooks.useCreate;

// Classes
export const classeHooks = createResourceHooks('classes', 'secondaire');
export const useClasses = () => useQuery({
  queryKey: ['classes', 'list'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/classes/classes/`),
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});
export const useClasse = (id, enabled = true) => useQuery({
  queryKey: ['classes', 'detail', id],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/classes/classes/${id}/`),
  enabled: enabled && !!id,
});

// Évaluations
export const evaluationHooks = createResourceHooks('evaluations', 'secondaire');
export const useEvaluations = (params = {}) => useQuery({
  queryKey: ['evaluations', 'list', params],
  queryFn: () => {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${getSecondaireApiUrl()}/notes/evaluations/?${queryString}` : `${getSecondaireApiUrl()}/notes/evaluations/`;
    return fetchApi(url);
  },
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});

// Bulletins
export const bulletinHooks = createResourceHooks('bulletins', 'secondaire');
export const useBulletins = bulletinHooks.useList;

// Présences
export const presenceHooks = createResourceHooks('presences', 'secondaire');
export const usePresences = presenceHooks.useList;

// Discipline
export const incidentHooks = createResourceHooks('incidents', 'secondaire');
export const sanctionHooks = createResourceHooks('sanctions', 'secondaire');
export const useIncidents = incidentHooks.useList;
export const useSanctions = sanctionHooks.useList;

// Cantine
export const cantineHooks = createResourceHooks('inscriptions-cantine', 'secondaire');
export const useCantine = cantineHooks.useList;

// Transport
export const transportHooks = createResourceHooks('lignes-transport', 'secondaire');
export const useTransport = transportHooks.useList;

// Infirmerie
export const infirmerieHooks = createResourceHooks('visites-infirmerie', 'secondaire');
export const useInfirmerie = infirmerieHooks.useList;

// Internat
export const internatHooks = createResourceHooks('chambres', 'secondaire');
export const useInternat = internatHooks.useList;

// Clubs
export const clubHooks = createResourceHooks('clubs', 'secondaire');
export const useClubs = clubHooks.useList;

// Conseil de classe
export const conseilClasseHooks = createResourceHooks('conseils-classe', 'secondaire');
export const useConseilsClasse = (params = {}) => useQuery({
  queryKey: ['conseils-classe', 'list', params],
  queryFn: () => {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${getSecondaireApiUrl()}/conseils/conseils-classe/?${queryString}` : `${getSecondaireApiUrl()}/conseils/conseils-classe/`;
    return fetchApi(url);
  },
  select: (data) => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  },
});

// Additional hooks for specific views
export const useEleveDetail = (id) => eleveHooks.useDetail(id);
export const useNotesByEleve = (eleveId) => useQuery({
  queryKey: ['notes-eleve', eleveId],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/notes/notes/?eleve=${eleveId}`),
  enabled: !!eleveId,
  select: (data) => (Array.isArray(data) ? data : data?.results || []),
});
export const usePresencesByEleve = (eleveId) => useQuery({
  queryKey: ['presences-eleve', eleveId],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/eleves/${eleveId}/presences/`),
  enabled: !!eleveId,
  select: (data) => (Array.isArray(data) ? data : data?.results || []),
});
export const useSecondaireMatieres = () => useQuery({
  queryKey: ['secondaire', 'matieres'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/classes/matieres/`),
  select: (data) => (Array.isArray(data) ? data : data?.results || []),
});
export const useEleveMatieresIndividuelles = (eleveId) => useQuery({
  queryKey: ['eleves', eleveId, 'matieres-individuelles'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/eleves/${eleveId}/matieres-individuelles/`),
  enabled: !!eleveId,
  select: (data) => (Array.isArray(data) ? data : data?.results || []),
});
export const useAjouterMatiereIndividuelleEleve = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eleveId, data }) => postApi(`${getSecondaireApiUrl()}/eleves/${eleveId}/matieres-individuelles/`, data),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ['eleves', variables.eleveId, 'matieres-individuelles'] });
      queryClient.invalidateQueries({ queryKey: ['eleves', 'detail', variables.eleveId] });
    },
  });
};
export const useRetirerMatiereIndividuelleEleve = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eleveId, affectationId }) => postApi(`${getSecondaireApiUrl()}/eleves/${eleveId}/retirer-matiere-individuelle/`, { affectation_id: affectationId }),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ['eleves', variables.eleveId, 'matieres-individuelles'] });
      queryClient.invalidateQueries({ queryKey: ['eleves', 'detail', variables.eleveId] });
    },
  });
};
export const useSemestres = (params = {}) => useQuery({
  queryKey: ['semestres', params],
  queryFn: () => {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${getSuperieurApiUrl()}/etablissement/semestres/?${queryString}` : `${getSuperieurApiUrl()}/etablissement/semestres/`;
    return fetchApi(url);
  },
  select: (data) => (Array.isArray(data) ? data : data?.results || []),
});
export const useECUEs = (params = {}) => useQuery({
  queryKey: ['ecues', params],
  queryFn: () => {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${getSuperieurApiUrl()}/ue-ecue/ecues/?${queryString}` : `${getSuperieurApiUrl()}/ue-ecue/ecues/`;
    return fetchApi(url);
  },
  select: (data) => (Array.isArray(data) ? data : data?.results || []),
});
export const useEtudiantMatieresIndividuelles = (etudiantId) => useQuery({
  queryKey: ['etudiants', etudiantId, 'matieres-individuelles'],
  queryFn: () => fetchApi(`${getSuperieurApiUrl()}/etudiants/${etudiantId}/matieres-individuelles/`),
  enabled: !!etudiantId,
  select: (data) => (Array.isArray(data) ? data : data?.results || []),
});
export const useAjouterMatiereIndividuelleEtudiant = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ etudiantId, data }) => postApi(`${getSuperieurApiUrl()}/etudiants/${etudiantId}/matieres-individuelles/`, data),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ['etudiants', variables.etudiantId, 'matieres-individuelles'] });
      queryClient.invalidateQueries({ queryKey: ['etudiants', 'detail', variables.etudiantId] });
    },
  });
};
export const useRetirerMatiereIndividuelleEtudiant = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ etudiantId, affectationId }) => postApi(`${getSuperieurApiUrl()}/etudiants/${etudiantId}/retirer-matiere-individuelle/`, { affectation_id: affectationId }),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ['etudiants', variables.etudiantId, 'matieres-individuelles'] });
      queryClient.invalidateQueries({ queryKey: ['etudiants', 'detail', variables.etudiantId] });
    },
  });
};

// Cantine extended
export const useInscritsCantin = () => useQuery({
  queryKey: ['inscrits-cantine'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/inscriptions-cantine/`),
});
export const useRepas = () => useQuery({
  queryKey: ['repas'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/repas/`),
});
export const useMenus = () => useQuery({
  queryKey: ['menus'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/menus/`),
});

// Transport extended
export const useInscritsTransport = () => useQuery({
  queryKey: ['inscrits-transport'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/inscriptions-transport/`),
});
export const useCircuits = () => useQuery({
  queryKey: ['circuits'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/circuits/`),
});
export const useVehicules = () => useQuery({
  queryKey: ['vehicules'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/vehicules/`),
});

// Infirmerie extended
export const useVisitesInfirmerie = () => useQuery({
  queryKey: ['visites-infirmerie'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/visites-infirmerie/`),
});
export const useDossiersMediaux = () => useQuery({
  queryKey: ['dossiers-medicaux'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/dossiers-medicaux/`),
});

// Internat extended
export const useInternes = () => useQuery({
  queryKey: ['internes'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/internes/`),
});
export const useChambres = () => useQuery({
  queryKey: ['chambres'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/chambres/`),
});

// Clubs extended
export const useMembresClub = (clubId) => useQuery({
  queryKey: ['membres-club', clubId],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/clubs/${clubId}/membres/`),
  enabled: !!clubId,
});
export const useActivitesClub = () => useQuery({
  queryKey: ['activites-club'],
  queryFn: () => fetchApi(`${getSecondaireApiUrl()}/activites-clubs/`),
});

// ============ ADMIN HOOKS ============

export const getAdminApiUrl = () => getConfig().SIS_ADMIN_API_URL || `${getConfig().LMS_BASE_URL}/api/sis/admin`;

export const getIntegrationApiUrl = () => `${getAdminApiUrl()}/integration`;
export const getCurrentEstablishmentUrl = () => `${getAdminApiUrl()}/etablissement/current/`;
export const normalizePageResponse = (data) => {
  if (Array.isArray(data)) {
    return {
      count: data.length, next: null, previous: null, results: data,
    };
  }
  return {
    count: data?.count || 0,
    next: data?.next || null,
    previous: data?.previous || null,
    results: data?.results || [],
  };
};

export const useIntegrationHealth = () => useQuery({
  queryKey: ['integration', 'health'],
  queryFn: () => fetchApi(`${getIntegrationApiUrl()}/health/`),
  staleTime: 30 * 1000,
});

export const useIntegrationStats = () => useQuery({
  queryKey: ['integration', 'stats'],
  queryFn: () => fetchApi(`${getIntegrationApiUrl()}/sync/status/`),
  staleTime: 30 * 1000,
});

export const useIntegrationUserMappings = (page = 1) => useQuery({
  queryKey: ['integration', 'user-mappings', page],
  queryFn: () => fetchApi(`${getIntegrationApiUrl()}/mappings/users/?page=${page}`),
  select: normalizePageResponse,
});

export const useIntegrationCourseMappings = (page = 1) => useQuery({
  queryKey: ['integration', 'course-mappings', page],
  queryFn: () => fetchApi(`${getIntegrationApiUrl()}/mappings/courses/?page=${page}`),
  select: normalizePageResponse,
});

export const useIntegrationOutboxEvents = (page = 1) => useQuery({
  queryKey: ['integration', 'outbox', page],
  queryFn: () => fetchApi(`${getIntegrationApiUrl()}/outbox/?page=${page}`),
  select: normalizePageResponse,
});

// Utilisateurs
export const utilisateurHooks = createResourceHooks('utilisateurs', 'admin');
export const useUtilisateurs = () => useQuery({
  queryKey: ['utilisateurs'],
  queryFn: () => fetchApi(`${getAdminApiUrl()}/utilisateurs/`),
});

// Structure pédagogique
export const useDepartements = () => useQuery({
  queryKey: ['departements'],
  queryFn: () => fetchApi(`${getAdminApiUrl()}/departements/`),
});
export const useNiveaux = () => useQuery({
  queryKey: ['niveaux'],
  queryFn: () => fetchApi(`${getAdminApiUrl()}/niveaux/`),
});
export const useMatieres = () => useQuery({
  queryKey: ['matieres'],
  queryFn: () => fetchApi(`${getAdminApiUrl()}/matieres/`),
});
