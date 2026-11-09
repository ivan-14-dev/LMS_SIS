import React, { useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Box, Button, Card, CardContent, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import { PageHeader, WorkflowHistoryPanel, WorkflowNotificationsPanel } from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { hasCapability } from '../../components/layout/navigation';
import { apiErrorMessage } from '../../services/resources';
import { financePage, financeRequest, paymentPayload } from './financeApi';

const today = () => new Date().toISOString().slice(0, 10);
const emptyPayment = () => ({
  facture: '',
  montant: '',
  mode: 'virement',
  reference_externe: '',
  date_paiement: today(),
  preuve_paiement: null,
});
const Field = props => <TextField size="small" fullWidth margin="dense" {...props} />;

const PaiementsPage = ({ apiType = 'superieur' }) => {
  const cache = useQueryClient();
  const capabilities = useCapabilities(apiType, { refetchOnMount: false });
  const manager = !capabilities.isFetching && !capabilities.error && hasCapability(capabilities.data, apiType === 'superieur' ? 'paiements.change_paiementfrais' : 'paiements.change_paiement');
  const [page, setPage] = useState(1);
  const [invoicePage, setInvoicePage] = useState(1);
  const [payment, setPayment] = useState(emptyPayment);
  const [selected, setSelected] = useState(null);
  const [receipt, setReceipt] = useState(null);
  const [reason, setReason] = useState('');
  const [refundReference, setRefundReference] = useState('');
  const [refundProof, setRefundProof] = useState(null);
  const [invoice, setInvoice] = useState({
    learner: '', type_frais: '', montant: '', devise: '', date_emission: today(), date_echeance: today(),
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const invoices = useQuery({
    queryKey: ['finance', apiType, 'invoices', invoicePage],
    queryFn: () => financePage(`factures/?page=${invoicePage}`, apiType),
  });
  const payments = useQuery({
    queryKey: ['finance', apiType, 'payments', page],
    queryFn: () => financePage(`transactions/?page=${page}`, apiType),
  });
  const providers = useQuery({
    queryKey: ['finance', apiType, 'providers'],
    queryFn: () => financeRequest('transactions/prestataires/', 'get', undefined, apiType),
  });
  const request = (path, method, data) => financeRequest(path, method, data, apiType);
  const perform = async (operation, message) => {
    if (sending.current) { return; }
    sending.current = true; setBusy(true); setError(''); setSuccess(''); setReceipt(null);
    try {
      await operation();
      await cache.invalidateQueries({ queryKey: ['finance', apiType] });
      await cache.invalidateQueries({ queryKey: ['workflow-notifications', apiType] });
      await cache.invalidateQueries({ queryKey: ['workflow-history', apiType] });
      setSuccess(message);
    } catch (failure) {
      setError(failure.response ? apiErrorMessage(failure) : failure.message);
    } finally { sending.current = false; setBusy(false); }
  };
  const settle = (operation, data = {}) => perform(
    () => request(`transactions/${selected.id}/${operation}/`, 'post', data),
    'Demande traitée par le serveur. Relisez le statut et le solde avant toute nouvelle opération.',
  );
  const downloadProof = operation => perform(async () => {
    const blob = await request(`transactions/${selected.id}/${operation}/`, 'get', { responseType: 'blob' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = `justificatif-${selected.numero}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, 'Justificatif privé reçu depuis le serveur.');
  const choose = row => {
    setSelected(row); setReason(''); setRefundReference(''); setRefundProof(null); setReceipt(null); setError(''); setSuccess('');
  };
  const paymentRows = payments.data?.results || [];
  const current = paymentRows.find(row => row.id === selected?.id);
  const invoiceRows = invoices.data?.results || [];
  const loadError = invoices.error || payments.error || providers.error || capabilities.error;
  return (
    <Box>
      <PageHeader title="Factures et paiements" subtitle="Déclaration, contrôle distinct et rapprochement serveur" />
      <Alert severity="info">
        Une déclaration ou un retour navigateur ne confirme aucun paiement.
        Les contrôles et reçus sont produits par le serveur.
        Aucun virement ni remboursement bancaire n’est déclenché ici.
      </Alert>
      {providers.data && (
      <Alert severity="warning" sx={{ my: 2 }}>
        Carte : {providers.data.carte}. Callback : {providers.data.callback}.
        Mobile money / SEPA : non configurés. Devise à choisir explicitement ; aucune règle fiscale appliquée.
      </Alert>
      )}
      {loadError && (
      <Alert severity="error">
        Chargement refusé ou indisponible : {apiErrorMessage(loadError)}
        <Button onClick={() => {
          invoices.refetch(); payments.refetch(); providers.refetch(); capabilities.refetch();
        }}
        >
          Recharger
        </Button>
      </Alert>
      )}
      {error && <Alert severity="error" sx={{ my: 2 }}>{error} En cas de coupure, rechargez avant de resoumettre.</Alert>}
      {success && <Alert severity="success" sx={{ my: 2 }}>{success}</Alert>}
      <WorkflowNotificationsPanel apiType={apiType} />
      <Card sx={{ my: 2 }}>
        <CardContent>
          <Typography variant="h5" component="h2">Factures accessibles</Typography>
          {invoices.isLoading && <Typography role="status">Chargement…</Typography>}
          {!invoices.isLoading && !invoices.error && !invoiceRows.length && (
            <Typography>Aucune facture accessible.</Typography>
          )}
          {invoiceRows.map(row => (
            <Stack key={row.id} direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ my: 2 }}>
              <Typography sx={{ flex: 1 }}>
                {row.numero} — {row.etudiant_nom || row.eleve_nom} — {row.montant}
                {' '}{row.devise || '(devise non configurée)'} — {row.statut}
              </Typography>
              <Button
                disabled={busy || !row.devise || !['emise', 'partielle', 'en_retard'].includes(row.statut)}
                onClick={() => setPayment({ ...emptyPayment(), facture: String(row.id) })}
              >Déclarer un paiement
              </Button>
              <Button
                disabled={busy}
                onClick={() => perform(async () => {
                  const balance = await request(`factures/${row.id}/${apiType === 'superieur' ? 'solde' : 'solde-confirme'}/`, 'get');
                  setReceipt({ facture: row.numero, devise: row.devise, ...balance });
                }, 'Solde recalculé depuis les paiements confirmés.')}
              >Solde confirmé
              </Button>
            </Stack>
          ))}
          <Button disabled={!invoices.data?.previous || busy} onClick={() => setInvoicePage(invoicePage - 1)}>
            Factures précédentes
          </Button>
          <Button disabled={!invoices.data?.next || busy} onClick={() => setInvoicePage(invoicePage + 1)}>
            Factures suivantes
          </Button>
        </CardContent>
      </Card>
      {payment.facture && (
      <Card sx={{ my: 2 }}>
        <CardContent>
          <Typography component="h2" variant="h5">Déclarer pour la facture #{payment.facture}</Typography>
          <Box
            component="form"
            onSubmit={event => {
              event.preventDefault();
              perform(
                async () => { await request('transactions/', 'post', paymentPayload(payment)); setPayment(emptyPayment()); },
                'Déclaration enregistrée en attente. Aucun encaissement confirmé.',
              );
            }}
          >
            <Field label="Montant" required value={payment.montant} onChange={event => setPayment({ ...payment, montant: event.target.value })} />
            <Field
              label="Date du paiement"
              type="date"
              required
              value={payment.date_paiement}
              onChange={event => setPayment({ ...payment, date_paiement: event.target.value })}
            />
            <Field label="Mode" select value={payment.mode} onChange={event => setPayment({ ...payment, mode: event.target.value })}>
              {['virement', 'especes', 'cheque'].map(mode => <MenuItem key={mode} value={mode}>{mode}</MenuItem>)}
              {providers.data?.carte === 'configure' && <MenuItem value="carte">Carte — référence Stripe existante</MenuItem>}
            </Field>
            <Field
              required
              label="Référence de rapprochement"
              value={payment.reference_externe}
              onChange={event => setPayment({ ...payment, reference_externe: event.target.value })}
            />
            <label htmlFor="payment-proof">Justificatif privé (PDF ou image)
              <input
                id="payment-proof"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                required={payment.mode !== 'carte'}
                onChange={event => setPayment({ ...payment, preuve_paiement: event.target.files[0] || null })}
              />
            </label>
            <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
              <Button type="submit" disabled={busy || Boolean(loadError)}>Soumettre au contrôle</Button>
              <Button disabled={busy} onClick={() => setPayment(emptyPayment())}>Annuler la saisie</Button>
            </Stack>
          </Box>
        </CardContent>
      </Card>
      )}
      {manager && (
      <Card sx={{ my: 2 }}>
        <CardContent>
          <Typography component="h2" variant="h5">Émettre une facture</Typography>
          <Box
            component="form"
            onSubmit={event => {
              event.preventDefault();
              const { learner: learnerId, ...values } = invoice;
              perform(
                () => request('factures/', 'post', { ...values, [apiType === 'superieur' ? 'etudiant' : 'eleve']: learnerId }),
                'Facture émise. Aucun paiement confirmé.',
              );
            }}
          >
            <Field
              required
              label="Identifiant du dossier apprenant existant"
              type="number"
              value={invoice.learner}
              onChange={event => setInvoice({ ...invoice, learner: event.target.value })}
            />
            <Field
              required
              label="Identifiant du tarif existant"
              type="number"
              value={invoice.type_frais}
              onChange={event => setInvoice({ ...invoice, type_frais: event.target.value })}
            />
            <Field
              required
              label="Montant de la facture"
              value={invoice.montant}
              onChange={event => setInvoice({ ...invoice, montant: event.target.value })}
            />
            <Field
              label="Devise explicite"
              select
              required
              value={invoice.devise}
              onChange={event => setInvoice({ ...invoice, devise: event.target.value })}
            >
              {(providers.data?.devises || []).map(code => <MenuItem key={code} value={code}>{code}</MenuItem>)}
            </Field>
            <Field
              type="date"
              required
              label="Émission"
              value={invoice.date_emission}
              onChange={event => setInvoice({ ...invoice, date_emission: event.target.value })}
            />
            <Field
              type="date"
              required
              label="Échéance"
              value={invoice.date_echeance}
              onChange={event => setInvoice({ ...invoice, date_echeance: event.target.value })}
            />
            <Button type="submit" disabled={busy || Boolean(loadError)}>Émettre</Button>
          </Box>
        </CardContent>
      </Card>
      )}
      <Card sx={{ my: 2 }}>
        <CardContent>
          <Typography component="h2" variant="h5">Paiements — page {page}</Typography>
          {payments.isLoading && <Typography role="status">Chargement…</Typography>}
          {!payments.isLoading && !payments.error && !paymentRows.length && (
          <Typography>Aucun paiement accessible.</Typography>
          )}
          {paymentRows.map(row => (
            <Stack key={row.id} direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ my: 2 }}>
              <Typography sx={{ flex: 1 }}>
                {row.numero} — {row.montant} {row.devise} — {row.statut} {row.motif_rejet}
              </Typography>
              <Button disabled={busy} onClick={() => choose(row)}>Consulter {row.numero}</Button>
            </Stack>
          ))}
          <Button disabled={!payments.data?.previous || busy} onClick={() => { setSelected(null); setPage(page - 1); }}>
            Précédents
          </Button>
          <Button disabled={!payments.data?.next || busy} onClick={() => { setSelected(null); setPage(page + 1); }}>
            Suivants
          </Button>
        </CardContent>
      </Card>
      {current && (
      <Card sx={{ my: 2 }}>
        <CardContent>
          <Typography component="h2" variant="h5">{current.numero} — {current.statut}</Typography>
          <Typography>
            Référence : {current.reference_externe}. Déclarant : {current.enregistre_par_nom || current.enregistre_par}.
          </Typography>
          <Typography>{current.motif_rejet}</Typography>
          {current.preuve_disponible && <Button disabled={busy} onClick={() => downloadProof('justificatif')}>Télécharger le justificatif</Button>}
          {current.remboursement?.demande_par && (
          <Button
            disabled={busy}
            onClick={() => downloadProof('justificatif-remboursement')}
          >Justificatif du remboursement
          </Button>
          )}
          {['valide', 'rembourse'].includes(current.statut) && (
          <Button
            disabled={busy}
            onClick={() => perform(async () => setReceipt(await request(`transactions/${current.id}/recu/`, 'get')), 'Reçu relu sur le serveur.')}
          >
            Lire le reçu
          </Button>
          )}
          {manager && (
          <>
            {['en_attente', 'echec'].includes(current.statut) && (
            <Button
              disabled={busy}
              onClick={() => settle('valider')}
            >Contrôler / rapprocher côté serveur
            </Button>
            )}
            {current.statut === 'en_attente' && (
            <>
              <Field label="Motif du rejet" value={reason} onChange={event => setReason(event.target.value)} />
              <Button disabled={busy || !reason.trim()} onClick={() => settle('rejeter', { motif: reason })}>Rejeter</Button>
            </>
            )}
            {current.statut === 'valide' && !current.remboursement?.demande_par && (
            <>
              <Field label="Motif du remboursement intégral" value={reason} onChange={event => setReason(event.target.value)} />
              <Field
                label="Référence du remboursement effectué hors SIS"
                value={refundReference}
                onChange={event => setRefundReference(event.target.value)}
              />
              <label htmlFor="refund-proof">Justificatif du remboursement
                <input id="refund-proof" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={event => setRefundProof(event.target.files[0] || null)} />
              </label>
              <Button
                disabled={busy || !reason.trim() || !refundReference.trim() || !refundProof}
                onClick={() => {
                  const payload = new FormData();
                  payload.append('motif', reason); payload.append('reference', refundReference); payload.append('preuve', refundProof);
                  settle('demander-remboursement', payload);
                }}
              >Soumettre le remboursement au contrôle distinct
              </Button>
            </>
            )}
            {current.statut === 'valide' && current.remboursement?.demande_par && (
            <>
              <Typography>
                Remboursement demandé par #{current.remboursement.demande_par} : {current.remboursement.motif}
              </Typography>
              <Button disabled={busy} onClick={() => settle('rembourser')}>Confirmer le remboursement après contrôle</Button>
            </>
            )}
          </>
          )}
        </CardContent>
      </Card>
      )}
      {receipt && (
      <Card sx={{ my: 2 }}>
        <CardContent>
          <Typography component="h2" variant="h5">Relevé serveur — non fiscal</Typography>
          <Box component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(receipt, null, 2)}</Box>
          <Button onClick={() => window.print()}>Imprimer</Button>
        </CardContent>
      </Card>
      )}
      <WorkflowHistoryPanel apiType={apiType} endpoint={current ? `paiements/transactions/${current.id}/historique/` : ''} title="Audit du paiement" />
    </Box>
  );
};

PaiementsPage.propTypes = { apiType: PropTypes.oneOf(['superieur', 'secondaire']) };
export default PaiementsPage;
