import React from 'react';
import { Badge, Button, Row, Col, Card } from '@openedx/paragon';
import { Add, Forum, Print } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useConseilsClasse } from '../../services/api';

const ConseilClassePage = () => {
  const { data: conseils = [], isLoading } = useConseilsClasse();

  const columns = [
    { Header: 'Date', accessor: 'date' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Trimestre', accessor: 'trimestre' },
    { Header: 'Président', accessor: 'president_nom' },
    { Header: 'Participants', accessor: 'nb_participants' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = {
          planifie: 'info',
          en_cours: 'warning',
          termine: 'success',
          annule: 'danger',
        };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
    {
      Header: 'PV',
      accessor: 'pv_disponible',
      Cell: ({ value }) => (
        value ? <Button size="sm" variant="outline-primary" iconBefore={Print}>PV</Button> : '—'
      ),
    },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: ({ row }) => (
        row.original.statut === 'planifie' ? (
          <Button size="sm" variant="outline-primary">Démarrer</Button>
        ) : null
      ),
    },
  ];

  const termines = conseils.filter(c => c.statut === 'termine').length;
  const planifies = conseils.filter(c => c.statut === 'planifie').length;

  return (
    <div>
      <PageHeader
        title="Conseils de classe"
        subtitle="Planification et suivi des conseils de classe"
        actions={[
          { label: 'Planifier conseil', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Total conseils" value={conseils.length} icon={<Forum />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Terminés" value={termines} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Planifiés" value={planifies} variant="info" />
        </Col>
        <Col md={3}>
          <StatCard title="Trimestre actif" value="T1" variant="warning" />
        </Col>
      </Row>

      <SISDataTable title="Conseils de classe" data={conseils} columns={columns} loading={isLoading} searchable exportable />

      <Row className="mt-4">
        <Col md={6}>
          <Card>
            <Card.Header><Card.Title>Ordre du jour type</Card.Title></Card.Header>
            <Card.Body>
              <ol>
                <li>Bilan général de la classe</li>
                <li>Examen des cas particuliers</li>
                <li>Attribution des appréciations</li>
                <li>Propositions d'orientation</li>
                <li>Questions diverses</li>
              </ol>
            </Card.Body>
          </Card>
        </Col>
        <Col md={6}>
          <Card>
            <Card.Header><Card.Title>Prochains conseils</Card.Title></Card.Header>
            <Card.Body>
              {conseils.filter(c => c.statut === 'planifie').slice(0, 5).map((c, i) => (
                <div key={i} className="py-2 border-bottom">
                  <strong>{c.classe_nom}</strong> - {c.date}
                </div>
              ))}
              {conseils.filter(c => c.statut === 'planifie').length === 0 && (
                <p className="text-muted mb-0">Aucun conseil planifié</p>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default ConseilClassePage;
