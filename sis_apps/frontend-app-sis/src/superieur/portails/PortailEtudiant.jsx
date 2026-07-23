import React from 'react';
import { Row, Col, Card, Button, Badge } from '@openedx/paragon';
import { useQuery } from '@tanstack/react-query';
import { PageHeader, StatCard, SISDataTable } from '../../components/common';
import { fetchApi, getSuperieurApiUrl } from '../../services/api';
import { Grade, CalendarMonth, Money, Book } from '@openedx/paragon/icons';

const PortailEtudiant = () => {
  const { data: profil } = useQuery({
    queryKey: ['portail-etudiant-profil'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-etudiant/mon-profil/`),
  });

  const { data: notes = [] } = useQuery({
    queryKey: ['portail-etudiant-notes'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-etudiant/mes-notes/`),
  });

  const { data: emploiDuTemps } = useQuery({
    queryKey: ['portail-etudiant-emploi'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/portail-etudiant/mon-emploi-du-temps/`),
  });

  const notesColumns = [
    { Header: 'ECUE', accessor: 'ecue_nom' },
    { Header: 'Type', accessor: 'type_evaluation' },
    { Header: 'Note', accessor: 'note', Cell: ({ value }) => `${value}/20` },
    { Header: 'Session', accessor: 'session' },
  ];

  return (
    <div>
      <PageHeader
        title="Mon espace étudiant"
        subtitle={profil ? `${profil.nom} ${profil.prenom} - ${profil.matricule}` : 'Chargement...'}
      />

      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Moyenne générale" value={profil?.moyenne || '—'} icon={<Grade />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Crédits ECTS" value={profil?.credits_valides || 0} icon={<Book />} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Cours cette semaine" value={emploiDuTemps?.nb_cours || 0} icon={<CalendarMonth />} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Bourse" value={profil?.bourse_active ? 'Active' : 'Non'} icon={<Money />} variant={profil?.bourse_active ? 'success' : 'secondary'} />
        </Col>
      </Row>

      <Row>
        <Col md={8}>
          <Card className="mb-4">
            <Card.Header><Card.Title>Mes notes récentes</Card.Title></Card.Header>
            <Card.Body>
              <SISDataTable
                title=""
                data={notes.slice(0, 10)}
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
            <Card.Header><Card.Title>Documents</Card.Title></Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                <Button variant="outline-primary">Certificat de scolarité</Button>
                <Button variant="outline-primary">Relevé de notes</Button>
                <Button variant="outline-primary">Attestation d'inscription</Button>
                <Button variant="outline-primary">Carte étudiant</Button>
              </div>
            </Card.Body>
          </Card>

          <Card>
            <Card.Header><Card.Title>Notifications</Card.Title></Card.Header>
            <Card.Body>
              <ul className="list-unstyled mb-0">
                <li className="py-2 border-bottom">
                  <Badge variant="info" className="me-2">Note</Badge>
                  Nouvelle note disponible
                </li>
                <li className="py-2 border-bottom">
                  <Badge variant="warning" className="me-2">Emploi du temps</Badge>
                  Changement de salle
                </li>
                <li className="py-2">
                  <Badge variant="success" className="me-2">Bourse</Badge>
                  Versement effectué
                </li>
              </ul>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PortailEtudiant;
