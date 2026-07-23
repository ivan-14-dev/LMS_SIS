import React, { useState } from 'react';
import { Row, Col, Card, Form, Button, Tabs, Tab } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useNotes, useFormations } from '../../services/api';

const NotesPage = () => {
  const [selectedFormation, setSelectedFormation] = useState('');
  const [selectedSession, setSelectedSession] = useState('normale');
  
  const { data: formations = [] } = useFormations();
  const { data: notes = [], isLoading } = useNotes({ formation: selectedFormation, session: selectedSession });

  const columns = [
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Matricule', accessor: 'etudiant_matricule' },
    { Header: 'ECUE', accessor: 'ecue_nom' },
    { Header: 'Type', accessor: 'type_evaluation' },
    { Header: 'Note', accessor: 'note', Cell: ({ value }) => `${value}/20` },
    { Header: 'Session', accessor: 'session' },
    { Header: 'Date', accessor: 'date_evaluation' },
  ];

  return (
    <div>
      <PageHeader
        title="Gestion des notes"
        subtitle="Saisie et consultation des notes"
      />

      <Card className="mb-4">
        <Card.Body>
          <Row>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Formation</Form.Label>
                <Form.Control
                  as="select"
                  value={selectedFormation}
                  onChange={(e) => setSelectedFormation(e.target.value)}
                >
                  <option value="">Toutes les formations</option>
                  {formations.map((f) => (
                    <option key={f.id} value={f.id}>{f.nom}</option>
                  ))}
                </Form.Control>
              </Form.Group>
            </Col>
            <Col md={3}>
              <Form.Group>
                <Form.Label>Session</Form.Label>
                <Form.Control
                  as="select"
                  value={selectedSession}
                  onChange={(e) => setSelectedSession(e.target.value)}
                >
                  <option value="normale">Session normale</option>
                  <option value="rattrapage">Session rattrapage</option>
                </Form.Control>
              </Form.Group>
            </Col>
            <Col md={3} className="d-flex align-items-end">
              <Button variant="primary">Saisir des notes</Button>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      <SISDataTable
        title="Relevé de notes"
        data={notes}
        columns={columns}
        loading={isLoading}
        searchable
        exportable
      />
    </div>
  );
};

export default NotesPage;
