import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { fetchApi, postApi } from '../services/api';
import { apiErrorMessage, fetchResourcePage, resourceUrl } from '../services/resources';
import StatusBadge from '../components/common/StatusBadge';

const statuses = {
  soumise: 'Soumise', en_cours: 'En cours', complement: 'Complément demandé', resolue: 'Réponse apportée', cloturee: 'Clôturée',
};
const categories = {
  resultat: 'Note ou résultat', inscription: 'Inscription', frais: 'Frais et paiement', autre: 'Autre demande',
};
const dateLabel = value => new Date(value).toLocaleString('fr');

const NewComplaint = ({ url, onClose, onCreated }) => {
  const [values, setValues] = useState({
    categorie: 'resultat', objet: '', description: '', reference_dossier: '',
  });
  const mutation = useMutation({ mutationFn: () => postApi(url, values), onSuccess: onCreated });
  const field = name => ({
    value: values[name], onChange: event => setValues({ ...values, [name]: event.target.value }),
  });
  return (
    <Dialog open onClose={mutation.isPending ? undefined : onClose} fullWidth maxWidth="sm">
      <form onSubmit={event => { event.preventDefault(); mutation.mutate(); }}>
        <DialogTitle>Nouvelle réclamation</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity="info">
              Votre demande reste privée. Elle ne modifie pas automatiquement une note ou un paiement.
              Vous pourrez ajouter vos justificatifs après l’envoi.
            </Alert>
            <TextField label="Catégorie" select slotProps={{ select: { native: true }, inputLabel: { shrink: true } }} {...field('categorie')}>
              {Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </TextField>
            <TextField label="Objet" required {...field('objet')} slotProps={{ htmlInput: { maxLength: 200 } }} />
            <TextField label="Référence du dossier concerné" {...field('reference_dossier')} slotProps={{ htmlInput: { maxLength: 200 } }} />
            <TextField label="Motif de la demande" multiline minRows={4} required {...field('description')} slotProps={{ htmlInput: { maxLength: 10000 } }} />
            {mutation.error && <Alert severity="error">{apiErrorMessage(mutation.error)}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={mutation.isPending}>Annuler</Button>
          <Button type="submit" variant="contained" disabled={mutation.isPending}>Envoyer la réclamation</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};
NewComplaint.propTypes = {
  url: PropTypes.string.isRequired, onClose: PropTypes.func.isRequired, onCreated: PropTypes.func.isRequired,
};

const ComplaintDetail = ({ url, id, agents }) => {
  const client = useQueryClient();
  const [message, setMessage] = useState('');
  const [agent, setAgent] = useState('');
  const [file, setFile] = useState(null);
  const [uploadKey, setUploadKey] = useState(0);
  const queryKey = ['complaint', url, id];
  const detail = useQuery({ queryKey, queryFn: () => fetchApi(`${url}${id}/`) });
  const mutation = useMutation({
    mutationFn: ({ endpoint, payload }) => postApi(`${url}${id}/${endpoint}/`, payload),
    onSuccess: (result) => {
      client.setQueryData(queryKey, result);
      client.invalidateQueries({ queryKey: ['complaints', url] });
      client.invalidateQueries({ queryKey: ['workflow-notifications'] });
      setMessage('');
      setFile(null);
      setUploadKey(value => value + 1);
    },
  });
  const download = useMutation({
    mutationFn: async (piece) => {
      const blob = await fetchApi(`${url}${id}/pieces/${piece.id}/telecharger/`, { responseType: 'blob' });
      const objectUrl = URL.createObjectURL(blob);
      try {
        const anchor = document.createElement('a');
        anchor.href = objectUrl;
        anchor.download = piece.nom;
        anchor.click();
      } finally {
        URL.revokeObjectURL(objectUrl);
      }
    },
  });
  if (detail.isLoading) { return <CircularProgress aria-label="Chargement du dossier" />; }
  if (detail.error) {
    return <Alert severity="error">Dossier indisponible. {apiErrorMessage(detail.error)}<Button onClick={() => detail.refetch()}>Réessayer</Button></Alert>;
  }
  const item = detail.data;
  const send = (endpoint, payload) => mutation.mutate({ endpoint, payload: { version: item.version, ...payload } });
  const transition = statut => send('transition', { statut, message });
  const upload = () => {
    const payload = new FormData();
    payload.append('fichier', file);
    payload.append('version', item.version);
    mutation.mutate({ endpoint: 'pieces', payload });
  };
  const canWrite = item.actions.echanger || item.actions.traiter || item.actions.recours || item.actions.cloturer;
  return (
    <Paper component="section" aria-label="Dossier de réclamation" variant="outlined" sx={{ p: { xs: 2, md: 3 }, mt: 3 }}>
      <Stack spacing={2}>
        <Stack direction="row" useFlexGap spacing={2} sx={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="h5" component="h2">{item.objet}</Typography>
            <Typography sx={{ overflowWrap: 'anywhere' }}>{item.reference}</Typography>
            <StatusBadge value={item.statut} label={statuses[item.statut]} />
          </Box>
          <Button onClick={() => detail.refetch()} disabled={detail.isFetching} sx={{ alignSelf: 'flex-start' }}>
            Actualiser
          </Button>
        </Stack>
        <Typography>Demandeur : {item.demandeur_nom} · Responsable : {item.responsable_nom || 'En attente d’affectation'}</Typography>
        <Typography>Catégorie : {categories[item.categorie]} · Référence concernée : {item.reference_dossier || 'Non précisée'}</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.description}</Typography>
        {item.decision && <Alert severity="info"><strong>Dernière décision motivée : </strong>{item.decision}</Alert>}
        {mutation.error && (
          <Alert severity="error">
            {apiErrorMessage(mutation.error)}
            <Button onClick={() => detail.refetch()}>Recharger le dossier</Button>
          </Alert>
        )}
        {item.actions.affecter && (
          <Stack spacing={1}>
            <TextField label="Agent responsable" value={agent} onChange={event => setAgent(event.target.value)} select slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}>
              <option value="">Choisir un agent habilité</option>
              {agents.map(user => <option key={user.id} value={user.id}>{user.nom}</option>)}
            </TextField>
            <Button onClick={() => send('affecter', { responsable: Number(agent) })} disabled={!agent || mutation.isPending}>Affecter le dossier</Button>
          </Stack>
        )}
        <Typography variant="h6" component="h3">Historique et échanges</Typography>
        {item.historique.map(entry => (
          <Box key={entry.id} sx={{ borderLeft: '3px solid', borderColor: 'divider', pl: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {dateLabel(entry.created_at)} · {entry.auteur_nom || 'Service habilité'} · {statuses[entry.statut]}
            </Typography>
            <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{entry.message}</Typography>
          </Box>
        ))}
        {canWrite && (
          <>
            <TextField label="Message ou motif de décision" multiline minRows={3} value={message} onChange={event => setMessage(event.target.value)} slotProps={{ htmlInput: { maxLength: 10000 } }} />
            <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap' }}>
              {item.actions.echanger && <Button disabled={!message.trim() || mutation.isPending} onClick={() => send('message', { message })}>Envoyer le message</Button>}
              {item.actions.traiter && item.statut !== 'complement' && <Button disabled={!message.trim() || mutation.isPending} onClick={() => transition('complement')}>Demander un complément</Button>}
              {item.actions.traiter && <Button variant="contained" disabled={!message.trim() || mutation.isPending} onClick={() => transition('resolue')}>Rendre la décision</Button>}
              {item.actions.cloturer && <Button disabled={!message.trim() || mutation.isPending} onClick={() => transition('cloturee')}>Clôturer</Button>}
              {item.actions.recours && <Button disabled={!message.trim() || mutation.isPending} onClick={() => transition('recours')}>Déposer un recours</Button>}
            </Stack>
          </>
        )}
        <Typography variant="h6" component="h3">Justificatifs privés</Typography>
        {download.error && <Alert severity="error">Téléchargement impossible. {apiErrorMessage(download.error)}</Alert>}
        {item.pieces.length === 0 && <Typography>Aucun justificatif.</Typography>}
        {item.pieces.map(piece => (
          <Button key={piece.id} onClick={() => download.mutate(piece)} disabled={download.isPending} sx={{ justifyContent: 'flex-start', overflowWrap: 'anywhere' }}>
            Télécharger {piece.nom}
          </Button>
        ))}
        {item.actions.echanger && (
          <>
            <Typography variant="body2">PDF uniquement, 25 Mo et 10 pièces maximum. Ne joignez que les informations nécessaires.</Typography>
            <input key={uploadKey} type="file" accept=".pdf" aria-label="Justificatif PDF" onChange={event => setFile(event.target.files[0] || null)} />
            <Button onClick={upload} disabled={!file || mutation.isPending}>Ajouter le justificatif</Button>
          </>
        )}
      </Stack>
    </Paper>
  );
};
ComplaintDetail.propTypes = {
  url: PropTypes.string.isRequired,
  id: PropTypes.string.isRequired,
  agents: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired, nom: PropTypes.string.isRequired,
  })).isRequired,
};

const ComplaintsPage = ({ variant }) => {
  const url = resourceUrl(variant, 'core/reclamations');
  const client = useQueryClient();
  const [parameters, setParameters] = useSearchParams();
  const id = parameters.get('dossier');
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('');
  const [creating, setCreating] = useState(false);
  const capabilities = useQuery({ queryKey: ['complaint-capabilities', url], queryFn: () => fetchApi(`${url}capacites/`) });
  const list = useQuery({
    queryKey: ['complaints', url, page, filter],
    queryFn: () => fetchResourcePage(url, { page, page_size: 20, statut: filter }),
    enabled: Boolean(capabilities.data) && !capabilities.isError,
  });
  const select = (value) => {
    const next = new URLSearchParams(parameters);
    next.set('dossier', value);
    setParameters(next);
  };
  return (
    <Box>
      <Typography variant="h4" component="h1">Réclamations</Typography>
      <Typography sx={{ my: 2 }}>
        Déposez et suivez vos demandes privées. Seuls le demandeur et le service habilité peuvent consulter le dossier.
      </Typography>
      {capabilities.isLoading && <CircularProgress aria-label="Chargement des habilitations" />}
      {capabilities.error && <Alert severity="error">Accès indisponible. {apiErrorMessage(capabilities.error)}<Button onClick={() => capabilities.refetch()}>Réessayer</Button></Alert>}
      {capabilities.data && !capabilities.isError && (
        <>
          {!id && (
          <>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ my: 2 }}>
              {capabilities.data.deposer && <Button variant="contained" onClick={() => setCreating(true)}>Nouvelle réclamation</Button>}
              <TextField label="Filtrer par statut" value={filter} onChange={event => { setFilter(event.target.value); setPage(1); }} select slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}>
                <option value="">Tous les statuts</option>
                {Object.entries(statuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </TextField>
              <Button onClick={() => { list.refetch(); client.invalidateQueries({ queryKey: ['complaint', url] }); }}>Actualiser</Button>
            </Stack>
            {list.isLoading && <CircularProgress aria-label="Chargement des réclamations" />}
            {list.error && <Alert severity="error">Liste indisponible. {apiErrorMessage(list.error)}</Alert>}
            {list.data && !list.error && (
            <>
              {list.data.count === 0 && <Alert severity="info">Aucune réclamation dans cette sélection.</Alert>}
              <TableContainer component={Paper} variant="outlined">
                <Table aria-label="Réclamations accessibles">
                  <TableHead>
                    <TableRow>
                      <TableCell>Objet</TableCell><TableCell>Statut</TableCell><TableCell>Dernière activité</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {list.data.results.map(item => (
                      <TableRow key={item.id}>
                        <TableCell><Button onClick={() => select(item.id)}>{item.objet}</Button></TableCell>
                        <TableCell><StatusBadge value={item.statut} label={statuses[item.statut]} /></TableCell>
                        <TableCell>{dateLabel(item.updated_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Button disabled={!list.data.previous} onClick={() => setPage(value => value - 1)}>Précédent</Button>
                <Typography>Page {page} · {list.data.count} dossiers</Typography>
                <Button disabled={!list.data.next} onClick={() => setPage(value => value + 1)}>Suivant</Button>
              </Stack>
            </>
            )}
          </>
          )}
          {id && (
            <>
              <Button onClick={() => {
                const next = new URLSearchParams(parameters);
                next.delete('dossier');
                setParameters(next);
              }}
              >Retour aux réclamations
              </Button>
              <ComplaintDetail key={`${url}${id}`} url={url} id={id} agents={capabilities.data.agents} />
            </>
          )}
          {creating && (
            <NewComplaint
              url={url}
              onClose={() => setCreating(false)}
              onCreated={(item) => {
                setCreating(false);
                select(item.id);
                client.invalidateQueries({ queryKey: ['complaints', url] });
                client.invalidateQueries({ queryKey: ['workflow-notifications'] });
              }}
            />
          )}
        </>
      )}
    </Box>
  );
};
ComplaintsPage.propTypes = { variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired };
export default ComplaintsPage;
