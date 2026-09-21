import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert, Button, Card, Col, Row, Spinner,
} from '@openedx/paragon';
import {
  EventNote, Grade, Money, Person,
} from '@openedx/paragon/icons';
import {
  PageHeader, SISDataTable, StatCard,
} from '../../components/common';
import { useCapabilities } from '../../components/auth/PermissionGuard';
import { fetchApi, getSecondaireApiUrl } from '../../services/api';

const PortailApprenantFamille = () => {
  const navigate = useNavigate();
  const { data: capabilities, isLoading: loadingCapabilities, isError: capabilitiesError } = useCapabilities('secondaire');
  const role = capabilities?.role || '';
  const isEleve = role === 'eleve';
  const isParent = role === 'parent';

  const { data: eleveDashboard, isLoading: loadingEleve } = useQuery({
    queryKey: ['secondaire-portail-apprenant-eleve-dashboard'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/eleve/tableau_bord/`),
    enabled: isEleve,
  });

  const { data: bulletins = [] } = useQuery({
    queryKey: ['secondaire-portail-apprenant-eleve-bulletins'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/eleve/bulletins/`),
    enabled: isEleve,
  });

  const { data: parentDashboard, isLoading: loadingParent } = useQuery({
    queryKey: ['secondaire-portail-apprenant-parent-dashboard'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail/parent/tableau_bord/`),
    enabled: isParent,
  });

  if (loadingCapabilities || (isEleve && loadingEleve) || (isParent && loadingParent)) {
    return <Spinner animation="border" screenReaderText="Chargement du portail" />;
  }

  if (capabilitiesError || (!isEleve && !isParent)) {
    return <Alert variant="danger">Ce portail est réservé aux élèves, étudiants et parents autorisés.</Alert>;
  }

  if (isEleve) {
    const stats = eleveDashboard?.statistiques || {};
    const notes = eleveDashboard?.notes_recentes || [];
    const notesColumns = [
      { Header: 'Évaluation', accessor: 'evaluation' },
      { Header: 'Matière', accessor: 'matiere' },
      { Header: 'Note', accessor: 'note' },
      { Header: 'Période', accessor: 'periode' },
      { Header: 'Date', accessor: 'date' },
    ];
    const bulletinColumns = [
      { Header: 'Période', accessor: 'periode' },
      { Header: 'Classe', accessor: 'classe' },
      { Header: 'Moyenne', accessor: 'moyenne' },
      { Header: 'Rang', accessor: 'rang' },
      { Header: 'Décision', accessor: 'decision' },
      { Header: 'Publié le', accessor: 'publie_le' },
    ];

    return (
      <div>
        <PageHeader
          title="Portail apprenant / famille"
          subtitle={eleveDashboard?.eleve ? `${eleveDashboard.eleve.nom} · ${eleveDashboard?.classe?.nom || 'Sans classe'}` : 'Espace élève'}
          actions={[
            { label: 'Évaluations', variant: 'primary', onClick: () => navigate('/secondaire/evaluations') },
            { label: 'Bulletins', variant: 'secondary', onClick: () => navigate('/secondaire/bulletins') },
          ]}
        />
        <Row className="mb-4">
          <Col md={3}>
            <StatCard title="Moyenne" value={stats.moyenne ?? '—'} icon={<Grade />} variant="primary" />
          </Col>
          <Col md={3}>
            <StatCard title="Rang" value={stats.rang ?? '—'} icon={<Person />} variant="success" />
          </Col>
          <Col md={3}>
            <StatCard title="Absences" value={stats.absences ?? 0} icon={<EventNote />} variant="warning" />
          </Col>
          <Col md={3}>
            <StatCard title="Retards" value={stats.retards ?? 0} icon={<EventNote />} variant="info" />
          </Col>
        </Row>
        <Row>
          <Col md={7}>
            <SISDataTable title="Notes récentes" data={notes} columns={notesColumns} searchable={false} exportable={false} />
          </Col>
          <Col md={5}>
            <SISDataTable title="Bulletins publiés" data={bulletins} columns={bulletinColumns} searchable={false} exportable={false} />
          </Col>
        </Row>
      </div>
    );
  }

  const enfants = parentDashboard?.enfants || [];
  const factures = parentDashboard?.factures_impayees || [];
  const enfantsColumns = [
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Classe', accessor: 'classe' },
    { Header: 'Niveau', accessor: 'niveau' },
    { Header: 'Moyenne', accessor: 'moyenne' },
    { Header: 'Rang', accessor: 'rang' },
    { Header: 'Absences', accessor: 'absences' },
    { Header: 'Retards', accessor: 'retards' },
  ];
  const facturesColumns = [
    { Header: 'Élève', accessor: 'eleve' },
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
        subtitle="Vue parent avec données limitées aux enfants autorisés"
      />
      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Enfants suivis" value={enfants.length} icon={<Person />} variant="primary" />
        </Col>
        <Col md={4}>
          <StatCard title="Factures impayées" value={factures.length} icon={<Money />} variant="warning" />
        </Col>
        <Col md={4}>
          <StatCard title="Absences cumulées" value={enfants.reduce((total, enfant) => total + (enfant.absences || 0), 0)} icon={<EventNote />} variant="info" />
        </Col>
      </Row>
      <Row>
        <Col md={8}>
          <SISDataTable title="Enfants autorisés" data={enfants} columns={enfantsColumns} searchable={false} exportable={false} />
        </Col>
        <Col md={4}>
          <Card>
            <Card.Header><Card.Title>Factures en attente</Card.Title></Card.Header>
            <Card.Body>
              <SISDataTable title="" data={factures} columns={facturesColumns} searchable={false} exportable={false} />
              <div className="d-grid gap-2 mt-3">
                <Button variant="outline-primary" onClick={() => navigate('/secondaire/bulletins')}>Voir les bulletins</Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PortailApprenantFamille;
