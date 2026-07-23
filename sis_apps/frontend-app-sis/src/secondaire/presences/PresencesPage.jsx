import React, { useState } from 'react';
import { Badge, Button, Row, Col, Form, Card } from '@openedx/paragon';
import { Save, Check } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { usePresences, useClasses } from '../../services/api';

const PresencesPage = () => {
  const [selectedClasse, setSelectedClasse] = useState('');
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const { data: presences = [], isLoading } = usePresences({ classe: selectedClasse, date: selectedDate });
  const { data: classes = [] } = useClasses();

  const columns = [
    { Header: 'Matricule', accessor: 'eleve_matricule' },
    { Header: 'Nom', accessor: 'eleve_nom' },
    { Header: 'Prénom', accessor: 'eleve_prenom' },
    {
      Header: 'Matin',
      accessor: 'present_matin',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'danger'}>{value ? 'P' : 'A'}</Badge>
      ),
    },
    {
      Header: 'Après-midi',
      accessor: 'present_apres_midi',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'danger'}>{value ? 'P' : 'A'}</Badge>
      ),
    },
    { Header: 'Justification', accessor: 'justification' },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: () => <Button size="sm" variant="outline-primary">Modifier</Button>,
    },
  ];

  const presents = presences.filter(p => p.present_matin && p.present_apres_midi).length;
  const absents = presences.filter(p => !p.present_matin || !p.present_apres_midi).length;

  return (
    <div>
      <PageHeader
        title="Présences"
        subtitle="Gestion des présences journalières"
        actions={[
          { label: 'Enregistrer', icon: <Save />, variant: 'primary', onClick: () => {} },
        ]}
      />

      <Card className="mb-4">
        <Card.Body>
          <Row>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Classe</Form.Label>
                <Form.Control
                  as="select"
                  value={selectedClasse}
                  onChange={(e) => setSelectedClasse(e.target.value)}
                >
                  <option value="">Toutes les classes</option>
                  {classes.map(c => (
                    <option key={c.id} value={c.id}>{c.nom}</option>
                  ))}
                </Form.Control>
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Date</Form.Label>
                <Form.Control
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                />
              </Form.Group>
            </Col>
            <Col md={4} className="d-flex align-items-end">
              <Button variant="outline-primary" iconBefore={Check}>Charger</Button>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      <Row className="mb-4">
        <Col md={4}>
          <StatCard title="Effectif" value={presences.length} variant="primary" />
        </Col>
        <Col md={4}>
          <StatCard title="Présents" value={presents} variant="success" />
        </Col>
        <Col md={4}>
          <StatCard title="Absents" value={absents} variant="danger" />
        </Col>
      </Row>

      <SISDataTable title="Feuille de présence" data={presences} columns={columns} loading={isLoading} searchable={false} exportable />
    </div>
  );
};

export default PresencesPage;
