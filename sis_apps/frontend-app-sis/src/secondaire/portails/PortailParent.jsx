import React from 'react';
import { Row, Col, Card, Button, Badge, Tabs, Tab } from '@openedx/paragon';
import { useQuery } from '@tanstack/react-query';
import { PageHeader, StatCard, SISDataTable } from '../../components/common';
import { fetchApi, getSecondaireApiUrl } from '../../services/api';
import { Grade, EventNote, Money, Message } from '@openedx/paragon/icons';

const PortailParent = () => {
  const { data: enfants = [] } = useQuery({
    queryKey: ['portail-parent-enfants'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail-parent/mes-enfants/`),
  });

  const { data: notifications = [] } = useQuery({
    queryKey: ['portail-parent-notifications'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail-parent/notifications/`),
  });

  const notesColumns = [
    { Header: 'Matière', accessor: 'matiere_nom' },
    { Header: 'Note', accessor: 'note', Cell: ({ value }) => `${value}/20` },
    { Header: 'Moyenne classe', accessor: 'moyenne_classe', Cell: ({ value }) => `${value}/20` },
    { Header: 'Date', accessor: 'date' },
  ];

  const absencesColumns = [
    { Header: 'Date', accessor: 'date' },
    { Header: 'Motif', accessor: 'motif' },
    {
      Header: 'Justifié',
      accessor: 'justifie',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'danger'}>{value ? 'Oui' : 'Non'}</Badge>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Espace Parents"
        subtitle="Suivi de la scolarité de vos enfants"
      />

      {enfants.length === 0 ? (
        <Card>
          <Card.Body>
            <p className="text-center text-muted mb-0">Aucun enfant associé à ce compte.</p>
          </Card.Body>
        </Card>
      ) : (
        <Tabs defaultActiveKey={enfants[0]?.id?.toString()}>
          {enfants.map(enfant => (
            <Tab key={enfant.id} eventKey={enfant.id.toString()} title={`${enfant.prenom} ${enfant.nom}`}>
              <div className="pt-4">
                <Row className="mb-4">
                  <Col md={3}>
                    <StatCard title="Moyenne" value={enfant.moyenne || '—'} icon={<Grade />} variant="primary" />
                  </Col>
                  <Col md={3}>
                    <StatCard title="Rang" value={enfant.rang ? `${enfant.rang}/${enfant.effectif}` : '—'} variant="success" />
                  </Col>
                  <Col md={3}>
                    <StatCard title="Absences" value={enfant.nb_absences || 0} icon={<EventNote />} variant={enfant.nb_absences > 3 ? 'danger' : 'info'} />
                  </Col>
                  <Col md={3}>
                    <StatCard title="Paiements" value={enfant.paiement_ok ? 'À jour' : 'En attente'} icon={<Money />} variant={enfant.paiement_ok ? 'success' : 'warning'} />
                  </Col>
                </Row>

                <Row>
                  <Col md={8}>
                    <Card className="mb-4">
                      <Card.Header><Card.Title>Dernières notes</Card.Title></Card.Header>
                      <Card.Body>
                        <SISDataTable
                          title=""
                          data={enfant.notes || []}
                          columns={notesColumns}
                          searchable={false}
                          exportable={false}
                          pageSize={5}
                        />
                      </Card.Body>
                    </Card>
                  </Col>
                  <Col md={4}>
                    <Card className="mb-4">
                      <Card.Header><Card.Title>Actions</Card.Title></Card.Header>
                      <Card.Body>
                        <div className="d-grid gap-2">
                          <Button variant="outline-primary">Voir le bulletin</Button>
                          <Button variant="outline-primary">Emploi du temps</Button>
                          <Button variant="outline-primary">Justifier absence</Button>
                          <Button variant="outline-primary">Contacter enseignant</Button>
                        </div>
                      </Card.Body>
                    </Card>
                  </Col>
                </Row>
              </div>
            </Tab>
          ))}
        </Tabs>
      )}

      <Card className="mt-4">
        <Card.Header><Card.Title>Notifications récentes</Card.Title></Card.Header>
        <Card.Body>
          {notifications.length === 0 ? (
            <p className="text-muted text-center mb-0">Aucune notification</p>
          ) : (
            <ul className="list-unstyled mb-0">
              {notifications.slice(0, 5).map((notif, i) => (
                <li key={i} className="py-2 border-bottom">
                  <Badge variant={notif.type === 'note' ? 'info' : notif.type === 'absence' ? 'warning' : 'primary'} className="me-2">
                    {notif.type}
                  </Badge>
                  {notif.message}
                  <br /><small className="text-muted">{notif.date}</small>
                </li>
              ))}
            </ul>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};

export default PortailParent;
