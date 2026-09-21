import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Card, Col, Row, Spinner,
} from '@openedx/paragon';
import {
  Grade, Money, School,
} from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, StatCard,
} from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { fetchApi, getSuperieurApiUrl } from '../../services/api';

const PortailApprenantFamille = () => {
  const navigate = useNavigate();
  const { data: capabilities, isLoading: loadingCapabilities, isError: capabilitiesError } = useCapabilities('superieur');
  const role = capabilities?.role || '';
  const isLearner = ['etudiant', 'doctorant'].includes(role);

  const { data: dashboard, isLoading: loadingDashboard } = useQuery({
    queryKey: ['superieur-portail-apprenant-dashboard'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/apprenant/tableau_bord/`),
    enabled: isLearner,
  });

  const { data: releves = [] } = useQuery({
    queryKey: ['superieur-portail-apprenant-releves'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail/apprenant/releves/`),
    enabled: isLearner,
  });

  if (loadingCapabilities || loadingDashboard) {
    return <Spinner animation="border" screenReaderText="Chargement du portail apprenant" />;
  }

  if (capabilitiesError || !isLearner) {
    return <Alert variant="danger">Ce portail est réservé aux étudiants autorisés.</Alert>;
  }

  const stats = dashboard?.statistiques || {};
  const notes = dashboard?.notes_recentes || [];
  const factures = dashboard?.factures_impayees || [];
  const notesColumns = [
    { Header: 'ECUE', accessor: 'ecue' },
    { Header: 'UE', accessor: 'ue' },
    { Header: 'Note', accessor: 'note' },
    { Header: 'Statut', accessor: 'statut' },
    { Header: 'Date', accessor: 'date' },
  ];
  const relevesColumns = [
    { Header: 'Semestre', accessor: 'semestre' },
    { Header: 'Moyenne', accessor: 'moyenne' },
    { Header: 'Crédits validés', accessor: 'credits_valides' },
    { Header: 'Mention', accessor: 'mention' },
    { Header: 'Date émission', accessor: 'date_emission' },
  ];
  const facturesColumns = [
    { Header: 'Numéro', accessor: 'numero' },
    { Header: 'Montant', accessor: 'montant' },
    { Header: 'Reste à payer', accessor: 'reste_a_payer' },
    { Header: 'Échéance', accessor: 'echeance' },
    { Header: 'Statut', accessor: 'statut' },
  ];

  return (
    <div>
      <PageHeader
        title="Portail apprenant / famille"
        subtitle={dashboard?.etudiant ? `${dashboard.etudiant.nom} · ${dashboard.etudiant.matricule}` : 'Espace étudiant'}
        actions={[
          { label: 'Notes', variant: 'primary', onClick: () => navigate('/superieur/notes') },
          { label: 'Paiements', variant: 'secondary', onClick: () => navigate('/superieur/paiements') },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Moyenne" value={stats.moyenne ?? '—'} icon={<Grade />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Crédits validés" value={stats.credits_valides ?? 0} icon={<School />} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Notes récentes" value={notes.length} icon={<Grade />} variant="info" />
        </Col>
        <Col md={3}>
          <StatCard title="Factures impayées" value={factures.length} icon={<Money />} variant="warning" />
        </Col>
      </Row>
      <Row>
        <Col md={7}>
          <SISDataTable title="Notes récentes" data={notes} columns={notesColumns} searchable={false} exportable={false} />
        </Col>
        <Col md={5}>
          <SISDataTable title="Relevés de notes" data={releves} columns={relevesColumns} searchable={false} exportable={false} />
          <Card className="mt-4">
            <Card.Header><Card.Title>Factures en attente</Card.Title></Card.Header>
            <Card.Body>
              <SISDataTable title="" data={factures} columns={facturesColumns} searchable={false} exportable={false} />
              <div className="d-grid gap-2 mt-3">
                <Button variant="outline-primary" onClick={() => navigate('/superieur/releves')}>Voir tous les relevés</Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PortailApprenantFamille;
