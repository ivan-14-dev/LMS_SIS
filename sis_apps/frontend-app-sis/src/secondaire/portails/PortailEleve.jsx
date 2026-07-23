import React from 'react';
import { Row, Col, Card, Button, Badge } from '@openedx/paragon';
import { useQuery } from '@tanstack/react-query';
import { PageHeader, StatCard, SISDataTable } from '../../components/common';
import { fetchApi, getSecondaireApiUrl } from '../../services/api';
import { Grade, CalendarMonth, EventNote, Class } from '@openedx/paragon/icons';

const PortailEleve = () => {
  const { data: profil } = useQuery({
    queryKey: ['portail-eleve-profil'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail-eleve/mon-profil/`),
  });

  const { data: notes = [] } = useQuery({
    queryKey: ['portail-eleve-notes'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail-eleve/mes-notes/`),
  });

  const { data: emploiDuTemps } = useQuery({
    queryKey: ['portail-eleve-emploi'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail-eleve/mon-emploi-du-temps/`),
  });

  const notesColumns = [
    { Header: 'Matière', accessor: 'matiere_nom' },
    { Header: 'Évaluation', accessor: 'evaluation_titre' },
    { Header: 'Note', accessor: 'note', Cell: ({ value }) => `${value}/20` },
    { Header: 'Moyenne classe', accessor: 'moyenne_classe', Cell: ({ value }) => `${value}/20` },
  ];

  return (
    <div>
      <PageHeader
        title="Mon espace élève"
        subtitle={profil ? `${profil.nom} ${profil.prenom} - ${profil.classe}` : 'Chargement...'}
      />

      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Moyenne générale" value={profil?.moyenne || '—'} icon={<Grade />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Rang" value={profil?.rang ? `${profil.rang}/${profil.effectif}` : '—'} icon={<Class />} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Cours aujourd'hui" value={emploiDuTemps?.cours_aujourdhui || 0} icon={<CalendarMonth />} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Absences" value={profil?.nb_absences || 0} icon={<EventNote />} variant={profil?.nb_absences > 3 ? 'danger' : 'info'} />
        </Col>
      </Row>

      <Row>
        <Col md={8}>
          <Card className="mb-4">
            <Card.Header><Card.Title>Mes dernières notes</Card.Title></Card.Header>
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
            <Card.Header><Card.Title>Prochains devoirs</Card.Title></Card.Header>
            <Card.Body>
              <ul className="list-unstyled mb-0">
                <li className="py-2 border-bottom">
                  <strong>Mathématiques</strong> - Contrôle ch. 3
                  <br /><small className="text-muted">Lundi 15 janvier</small>
                </li>
                <li className="py-2 border-bottom">
                  <strong>Français</strong> - Rédaction
                  <br /><small className="text-muted">Mercredi 17 janvier</small>
                </li>
                <li className="py-2">
                  <strong>Histoire-Géo</strong> - Évaluation
                  <br /><small className="text-muted">Vendredi 19 janvier</small>
                </li>
              </ul>
            </Card.Body>
          </Card>

          <Card>
            <Card.Header><Card.Title>Documents</Card.Title></Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                <Button variant="outline-primary">Mon bulletin</Button>
                <Button variant="outline-primary">Emploi du temps</Button>
                <Button variant="outline-primary">Certificat de scolarité</Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PortailEleve;
