import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Stack, Typography,
} from '@mui/material';
import { hasCapability } from '../../components/layout/navigation';
import { fetchApi } from '../../services/api';
import { downloadPdf, resourceUrl } from '../../services/resources';
import LibraryBookEditor from './LibraryBookEditor';
import LibraryLoanDialog from './LibraryLoanDialog';
import { libraryQueryOptions, reservationResource } from './libraryUi';

const LibraryBook = ({
  variant, id, capabilities, busy, onBusy, onError, onRefresh, onCommand,
}) => {
  const base = resourceUrl(variant, 'bibliotheque');
  const [editing, setEditing] = useState(false);
  const [borrowing, setBorrowing] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const downloading = useRef(false);
  const mounted = useRef(true);
  const can = permission => hasCapability(capabilities, `bibliotheque.${permission}`);
  const manage = can('change_livre');
  const detail = useQuery({
    ...libraryQueryOptions,
    queryKey: ['library', base, 'book', id],
    queryFn: ({ signal }) => fetchApi(`${base}livres/${id}/`, { signal }),
  });
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    if (detail.error) { onError(detail.error); }
  }, [detail.error, onError]);
  useEffect(() => { setDownloaded(false); }, [detail.dataUpdatedAt]);
  const download = async () => {
    if (busy || downloading.current) { return; }
    downloading.current = true;
    setDownloaded(false);
    onBusy(true);
    try {
      // Never follow the serializer's URL: the session endpoint rechecks the licence on each request.
      await downloadPdf(`${base}livres/${id}/numerique/`, `livre-${id}.pdf`);
      if (mounted.current) { setDownloaded(true); }
    } catch (error) {
      onError(error);
    } finally {
      downloading.current = false;
      onBusy(false);
    }
  };
  if (detail.error) { return null; }
  if (detail.isFetching || !detail.data) { return <Typography>Chargement du livre…</Typography>; }
  const book = detail.data;
  const available = can('consulter_ressource_numerique')
    && book.licence_active === true && book.peut_consulter_ressource === true;
  let unavailable = 'Ressource numérique indisponible : fichier absent, licence expirée ou accès non autorisé par le serveur.';
  if (!book.licence_active) { unavailable = 'Ressource numérique indisponible : licence inactive ou révoquée.'; }
  if (!can('consulter_ressource_numerique')) { unavailable = 'Consultation numérique indisponible : habilitation explicite requise.'; }
  return (
    <Stack spacing={2}>
      <Typography variant="h5" component="h2">{book.titre}</Typography>
      <Typography>{book.auteurs}</Typography>
      {book.resume && <Typography sx={{ whiteSpace: 'pre-wrap' }}>{book.resume}</Typography>}
      {book.licence_expire_le && <Typography>Échéance de licence : {book.licence_expire_le}</Typography>}
      <Alert severity="info">
        L’accès au fichier est contrôlé à chaque téléchargement. Une révocation ne peut pas effacer
        une copie déjà téléchargée sur votre appareil.
      </Alert>
      {!available && <Alert severity="warning">{unavailable}</Alert>}
      <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap' }}>
        {available && <Button disabled={busy} onClick={download}>Télécharger le PDF autorisé</Button>}
        {manage && (
          <Button disabled={busy} onClick={() => { setEditing(true); setDownloaded(false); }}>
            Gérer le fichier et la licence
          </Button>
        )}
        {(can('add_emprunt') || manage) && (
          <Button disabled={busy} onClick={() => { setBorrowing(true); setDownloaded(false); }}>
            Emprunter un exemplaire
          </Button>
        )}
        {(can('add_reservation') || manage) && (
          <Button
            disabled={busy}
            onClick={() => {
              setDownloaded(false);
              onCommand(`${base}${reservationResource(variant)}/`, { livre: id });
            }}
          >Réserver ce titre pour moi
          </Button>
        )}
      </Stack>
      {downloaded && available && <Alert severity="success">PDF reçu ; téléchargement transmis à votre navigateur.</Alert>}
      {editing && manage && (
        <LibraryBookEditor
          book={book}
          url={`${base}livres/${id}/`}
          busy={busy}
          onBusy={onBusy}
          onClose={() => setEditing(false)}
          onSaved={onRefresh}
          onError={onError}
        />
      )}
      {borrowing && (
        <LibraryLoanDialog
          variant={variant}
          livre={id}
          title={book.titre}
          busy={busy}
          onClose={() => setBorrowing(false)}
          onError={onError}
          onSubmit={async payload => {
            await onCommand(`${base}emprunts/`, payload);
            if (mounted.current) { setBorrowing(false); }
          }}
        />
      )}
    </Stack>
  );
};
LibraryBook.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur']).isRequired,
  id: PropTypes.number.isRequired,
  capabilities: PropTypes.shape({ permissions: PropTypes.arrayOf(PropTypes.string) }).isRequired,
  busy: PropTypes.bool.isRequired,
  onBusy: PropTypes.func.isRequired,
  onError: PropTypes.func.isRequired,
  onRefresh: PropTypes.func.isRequired,
  onCommand: PropTypes.func.isRequired,
};
export default LibraryBook;
