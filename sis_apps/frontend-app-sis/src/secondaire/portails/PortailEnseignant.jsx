import React from 'react';
import { Row, Col, Card, Button } from '@openedx/paragon';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  PageHeader, StatCard, SISDataTable, WorkflowNotificationsPanel,
} from '../../components/common';
import { fetchApi, getSecondaireApiUrl } from '../../services/api';
import { People, CalendarMonth, Grade, Class } from '@openedx/paragon/icons';

const PortailEnseignantSecondaire = () => {
  const navigate = useNavigate();
  const { data: profil } = useQuery({
    queryKey: ['portail-enseignant-sec-profil'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail-enseignant/mon-profil/`),
  });

  const { data: cours = [] } = useQuery({
    queryKey: ['portail-enseignant-sec-cours'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail-enseignant/mes-cours/`),
  });

  const { data: classes = [] } = useQuery({
    queryKey: ['portail-enseignant-sec-classes'],
    queryFn: () => fetchApi(`${getSecondaireApiUrl()}/portail-enseignant/mes-classes/`),
  });

  const coursColumns = [
    { Header: 'Jour', accessor: 'jour_display' },
    { Header: 'Horaire', accessor: 'horaire' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Matière', accessor: 'matiere_nom' },
    { Header: 'Salle', accessor: 'salle' },
  ];

  const classesColumns = [
    { Header: 'Classe', accessor: 'nom' },
    { Header: 'Effectif', accessor: 'effectif' },
    { Header: 'Matière', accessor: 'matiere_nom' },
    { Header: 'Notes saisies', accessor: 'notes_saisies' },
    { Header: 'Moy. classe', accessor: 'moyenne', Cell: ({ value }) => value ? `${value}/20` : '—' },
  ];

  return (
    <div>
      <PageHeader
        title="Mon espace enseignant"
        subtitle={profil ? `${profil.civilite} ${profil.nom} ${profil.prenom}` : 'Chargement...'}
        actions={[
          { label: 'Évaluations', variant: 'primary', onClick: () => navigate('/secondaire/evaluations') },
          { label: 'Workflows', variant: 'secondary', onClick: () => navigate('/secondaire/workflows') },
        ]}
      />
      <WorkflowNotificationsPanel apiType="secondaire" title="Notifications workflow de l’enseignant" />

      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Mes classes" value={classes.length} icon={<Class />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Mes élèves" value={profil?.nb_eleves || 0} icon={<People />} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Cours cette semaine" value={cours.length} icon={<CalendarMonth />} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Notes à saisir" value={profil?.notes_en_attente || 0} icon={<Grade />} variant="info" />
        </Col>
      </Row>

      <Row>
        <Col md={8}>
          <Card className="mb-4">
            <Card.Header><Card.Title>Mon emploi du temps</Card.Title></Card.Header>
            <Card.Body>
              <SISDataTable
                title=""
                data={cours}
                columns={coursColumns}
                searchable={false}
                exportable
              />
            </Card.Body>
          </Card>

          <Card>
            <Card.Header><Card.Title>Mes classes</Card.Title></Card.Header>
            <Card.Body>
              <SISDataTable
                title=""
                data={classes}
                columns={classesColumns}
                searchable={false}
                exportable
              />
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="mb-4">
            <Card.Header><Card.Title>Actions rapides</Card.Title></Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                <Button variant="primary" onClick={() => navigate('/secondaire/evaluations')}>Saisir des notes</Button>
                <Button variant="outline-primary" onClick={() => navigate('/secondaire/presences')}>Saisir les absences</Button>
                <Button variant="outline-primary" onClick={() => navigate('/secondaire/classes')}>Mes classes</Button>
                <Button variant="outline-primary" onClick={() => navigate('/secondaire/workflows')}>Centre workflow</Button>
              </div>
            </Card.Body>
          </Card>

          <Card>
            <Card.Header><Card.Title>Conseil de classe</Card.Title></Card.Header>
            <Card.Body>
              <p className="mb-2"><strong>Prochain conseil:</strong></p>
              <p className="text-muted">
                {profil?.prochain_conseil ? (
                  <>
                    {profil.prochain_conseil.classe} - {profil.prochain_conseil.date}
                  </>
                ) : (
                  'Aucun conseil prévu'
                )}
              </p>
              <Button variant="outline-primary" size="sm" onClick={() => navigate('/secondaire/conseil-classe')}>Voir tous les conseils</Button>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default PortailEnseignantSecondaire;
