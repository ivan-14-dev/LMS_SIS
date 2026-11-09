import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { SISDataTable } from '../../components/common';
import RecordsTabs from '../../components/common/RecordsTabs';
import { fetchApi, getSecondaireApiUrl } from '../../services/api';
import { apiErrorMessage, downloadPdf } from '../../services/resources';

const ChildRecord = ({ childId }) => {
  const [downloadError, setDownloadError] = useState('');
  const [downloading, setDownloading] = useState(false);
  const record = useQuery({
    queryKey: ['family-child-record', childId],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/apprenant/dossier_enfant/?enfant_id=${childId}`),
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
    retry: false,
  });
  const download = async (id) => {
    setDownloadError('');
    setDownloading(true);
    try {
      await downloadPdf(`${getSecondaireApiUrl()}/bulletins/${id}/pdf_officiel/`, `bulletin-${id}.pdf`);
    } catch (error) {
      setDownloadError(apiErrorMessage(error));
      record.refetch();
    } finally {
      setDownloading(false);
    }
  };
  if (record.isPending || record.isFetching) {
    return <Typography role="status">Vérification du dossier autorisé…</Typography>;
  }
  if (record.error || !record.data) {
    return <Alert severity="error">Dossier indisponible ou liaison retirée. {apiErrorMessage(record.error)}</Alert>;
  }
  const { data } = record;
  const table = (title, rows, columns) => (
    <SISDataTable title={title} showTitle={false} data={rows || []} columns={columns} searchable={false} exportable={false} />
  );
  return (
    <Box>
      <Typography component="h2" variant="h6">{data.enfant?.nom}</Typography>
      <Button onClick={() => record.refetch()}>Actualiser le dossier</Button>
      {downloadError && <Alert severity="error">{downloadError}</Alert>}
      <RecordsTabs label="Dossier de l’enfant" panels={[
        { label: 'Notes récentes', content: table('Notes récentes', data.notes, [
          { Header: 'Matière', accessor: 'matiere' }, { Header: 'Évaluation', accessor: 'evaluation' },
          { Header: 'Note', accessor: 'note' }, { Header: 'Statut', accessor: 'statut' }, { Header: 'Date', accessor: 'date' },
        ]) },
        { label: 'Absences et retards', content: table('Absences et retards', data.absences, [
          { Header: 'Date', accessor: 'date' }, { Header: 'Statut', accessor: 'statut' },
          { Header: 'Retard (minutes)', accessor: 'retard_minutes' },
        ]) },
        { label: 'Planning', content: table('Planning', data.planning, [
          { Header: 'Jour (1 = lundi)', accessor: 'jour' }, { Header: 'Début', accessor: 'heure_debut' },
          { Header: 'Fin', accessor: 'heure_fin' }, { Header: 'Matière', accessor: 'matiere' },
          { Header: 'Enseignant', accessor: 'enseignant' }, { Header: 'Salle', accessor: 'salle' },
        ]) },
        { label: 'Factures et paiements', content: <Stack spacing={2}>
          {table('Factures', data.factures, [
            { Header: 'Numéro', accessor: 'numero' }, { Header: 'Statut', accessor: 'statut' },
            { Header: 'Montant', accessor: 'montant' }, { Header: 'Payé', accessor: 'montant_paye' },
            { Header: 'Reste à payer', accessor: 'reste_a_payer' },
          ])}
          {table('Paiements', (data.factures || []).flatMap(invoice => invoice.paiements.map(payment => ({ ...payment, facture: invoice.numero }))), [
            { Header: 'Facture', accessor: 'facture' }, { Header: 'Numéro', accessor: 'numero' },
            { Header: 'Date', accessor: 'date' }, { Header: 'Montant', accessor: 'montant' },
            { Header: 'Statut', accessor: 'statut' },
          ])}
        </Stack> },
        { label: 'Bulletins publiés', content: <Stack spacing={1}>
          {(data.bulletins || []).map(bulletin => (
            <Box key={bulletin.id}>
              <Typography>{bulletin.periode} · {bulletin.classe} · Moyenne : {bulletin.moyenne ?? '—'}</Typography>
              <Button disabled={downloading} onClick={() => download(bulletin.id)}>Télécharger le bulletin {bulletin.id}</Button>
            </Box>
          ))}
          {data.bulletins?.length === 0 && <Typography>Aucun bulletin publié.</Typography>}
        </Stack> },
      ]} />
    </Box>
  );
};

ChildRecord.propTypes = { childId: PropTypes.number.isRequired };

const ChildFamilyRecord = ({ pupils }) => {
  const [selectedId, setSelectedId] = useState('');
  const selected = pupils.find(child => child.id === Number(selectedId));
  return (
    <Box sx={{ mt: 3 }}>
      <TextField select label="Consulter le dossier d’un enfant" value={selected ? selectedId : ''} onChange={event => setSelectedId(event.target.value)} fullWidth>
        {pupils.map(child => <MenuItem key={child.id} value={child.id}>{child.nom}</MenuItem>)}
      </TextField>
      {pupils.length === 0 && <Alert severity="info">Aucun enfant autorisé. Contactez l’établissement pour votre liaison.</Alert>}
      {selected && <ChildRecord key={selected.id} childId={selected.id} />}
    </Box>
  );
};

ChildFamilyRecord.propTypes = { pupils: PropTypes.arrayOf(PropTypes.shape({ id: PropTypes.number, nom: PropTypes.string })).isRequired };

export default ChildFamilyRecord;
