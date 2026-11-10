import React from 'react';
import { useOutletContext } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Typography,
} from '@mui/material';
import { fetchApi } from '../../services/api';
import { apiErrorMessage, resourceUrl } from '../../services/resources';
import { canEnterPortal } from './navigation';
import SISDataTable from '../common/SISDataTable';

const columns = [
  { Header: 'Jour', accessor: 'jour' },
  { Header: 'Début', accessor: 'debut' },
  { Header: 'Fin', accessor: 'fin' },
  { Header: 'Cours', accessor: 'cours' },
  { Header: 'Salle', accessor: 'salle' },
  { Header: 'Classe / groupe', accessor: 'groupe' },
  { Header: 'Période et fréquence', accessor: 'periode' },
];

const PersonalTimetable = () => {
  const { variant, capabilities, searchContext } = useOutletContext();
  const allowed = canEnterPortal(capabilities, 'learner');
  const timetable = useQuery({
    queryKey: ['personal-timetable', variant, searchContext],
    queryFn: () => fetchApi(resourceUrl(variant, 'portail/apprenant/emploi_du_temps')),
    enabled: allowed && Boolean(searchContext),
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
  });
  if (!allowed) { return <Alert severity="error">Cet emploi du temps est réservé à votre profil apprenant.</Alert>; }
  if (!searchContext || timetable.isLoading || timetable.isFetching) {
    return <Typography role="status">Chargement de votre emploi du temps…</Typography>;
  }
  if (timetable.isError) {
    return (
      <Alert severity="error" action={<Button onClick={() => timetable.refetch()}>Réessayer</Button>}>
        Impossible de charger votre emploi du temps. {apiErrorMessage(timetable.error)}
      </Alert>
    );
  }
  if (!Array.isArray(timetable.data)) {
    return <Alert severity="error">La réponse de l’emploi du temps est invalide.</Alert>;
  }
  return (
    <>
      <Typography component="h1" variant="h4" sx={{ mb: 2 }}>Mon emploi du temps</Typography>
      <Typography sx={{ mb: 2 }}>
        Créneaux associés à votre scolarité actuelle et aux groupes qui vous sont attribués.
      </Typography>
      {timetable.data?.length === 0 && (
        <Alert severity="info">Aucun créneau n’est actuellement associé à votre scolarité.</Alert>
      )}
      <SISDataTable title="Mes créneaux" columns={columns} data={timetable.data} searchable={false} exportable={false} />
    </>
  );
};
export default PersonalTimetable;
