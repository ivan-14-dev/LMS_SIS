import React, { useState } from 'react';
import { Row, Col, Card, Badge, Button, Form, Modal, ActionRow, Tabs, Tab } from '@openedx/paragon';
import { Add, CalendarMonth, Room, Person } from '@openedx/paragon/icons';
import { useQuery } from '@tanstack/react-query';
import { PageHeader, SISDataTable } from '../../components/common';
import { 
  useCreneauxCours, useSalles, useReservations,
  useFormations, fetchApi, getSuperieurApiUrl 
} from '../../services/api';

const JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];
const HEURES = ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00'];

const EmploiDuTempsPage = () => {
  const [view, setView] = useState('formation'); // formation, enseignant, salle
  const [selectedFormation, setSelectedFormation] = useState('');
  const [selectedSemestre, setSelectedSemestre] = useState('');
  const [showReservation, setShowReservation] = useState(false);

  const { data: formations = [] } = useFormations();
  const { data: salles = [] } = useSalles();
  const { data: reservations = [] } = useReservations();

  const { data: emploiDuTemps } = useQuery({
    queryKey: ['emploi-du-temps', selectedFormation, selectedSemestre],
    queryFn: () => fetchApi(
      `${getSuperieurApiUrl()}/creneaux-cours/par_formation/?formation_id=${selectedFormation}&semestre_id=${selectedSemestre}`
    ),
    enabled: !!selectedFormation && !!selectedSemestre,
  });

  const sallesColumns = [
    { Header: 'Code', accessor: 'code' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Bâtiment', accessor: 'batiment_code' },
    { Header: 'Type', accessor: 'type_display' },
    { Header: 'Capacité', accessor: 'capacite' },
    {
      Header: 'Disponible',
      accessor: 'disponible',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'danger'}>
          {value ? 'Oui' : 'Non'}
        </Badge>
      ),
    },
  ];

  const reservationsColumns = [
    { Header: 'Salle', accessor: 'salle_code' },
    { Header: 'Date', accessor: 'date' },
    { Header: 'Horaire', accessor: 'heure_debut', Cell: ({ row }) => `${row.original.heure_debut} - ${row.original.heure_fin}` },
    { Header: 'Demandeur', accessor: 'demandeur_nom' },
    { Header: 'Motif', accessor: 'motif_display' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = {
          en_attente: 'warning',
          confirmee: 'success',
          refusee: 'danger',
          annulee: 'secondary',
        };
        return <Badge variant={variants[value]}>{value}</Badge>;
      },
    },
  ];

  // Grille d'emploi du temps
  const renderTimeGrid = () => {
    if (!emploiDuTemps?.emploi_du_temps) {
      return <p className="text-muted text-center py-4">Sélectionnez une formation et un semestre</p>;
    }

    return (
      <div className="table-responsive">
        <table className="table table-bordered">
          <thead>
            <tr>
              <th style={{ width: '80px' }}>Heure</th>
              {JOURS.map((jour) => (
                <th key={jour}>{jour}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {HEURES.map((heure, idx) => (
              <tr key={heure}>
                <td className="text-muted small">{heure}</td>
                {JOURS.map((jour, jourIdx) => {
                  const creneaux = emploiDuTemps.emploi_du_temps[jourIdx]?.filter(
                    c => c.horaire?.startsWith(heure.split(':')[0])
                  ) || [];
                  
                  return (
                    <td key={jour} className="p-1">
                      {creneaux.map((creneau, i) => (
                        <div 
                          key={i}
                          className="p-2 rounded mb-1"
                          style={{ 
                            backgroundColor: creneau.type_cours === 'CM' ? '#e3f2fd' : 
                                           creneau.type_cours === 'TD' ? '#e8f5e9' : '#fff3e0',
                            fontSize: '0.8rem'
                          }}
                        >
                          <strong>{creneau.ecue_code}</strong>
                          <br />
                          <small>{creneau.type_display}</small>
                          <br />
                          <small className="text-muted">
                            {creneau.salle_code} - {creneau.enseignant_nom}
                          </small>
                        </div>
                      ))}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div>
      <PageHeader
        title="Emploi du temps"
        subtitle="Gestion des créneaux et réservations de salles"
        actions={
          <>
            <Button variant="outline-primary" onClick={() => setShowReservation(true)}>
              Réserver une salle
            </Button>
            <Button variant="primary" iconBefore={Add}>
              Nouveau créneau
            </Button>
          </>
        }
      />

      <Card className="mb-4">
        <Card.Body>
          <Tabs defaultActiveKey="emploi">
            <Tab eventKey="emploi" title="Emploi du temps">
              <div className="pt-3">
                <Row className="mb-3">
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label>Vue par</Form.Label>
                      <Form.Control
                        as="select"
                        value={view}
                        onChange={(e) => setView(e.target.value)}
                      >
                        <option value="formation">Formation</option>
                        <option value="enseignant">Enseignant</option>
                        <option value="salle">Salle</option>
                      </Form.Control>
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group>
                      <Form.Label>Formation</Form.Label>
                      <Form.Control
                        as="select"
                        value={selectedFormation}
                        onChange={(e) => setSelectedFormation(e.target.value)}
                      >
                        <option value="">Sélectionner...</option>
                        {formations.map((f) => (
                          <option key={f.id} value={f.id}>{f.nom}</option>
                        ))}
                      </Form.Control>
                    </Form.Group>
                  </Col>
                  <Col md={3}>
                    <Form.Group>
                      <Form.Label>Semestre</Form.Label>
                      <Form.Control
                        as="select"
                        value={selectedSemestre}
                        onChange={(e) => setSelectedSemestre(e.target.value)}
                      >
                        <option value="">Sélectionner...</option>
                        <option value="1">Semestre 1</option>
                        <option value="2">Semestre 2</option>
                      </Form.Control>
                    </Form.Group>
                  </Col>
                  <Col md={2} className="d-flex align-items-end">
                    <Button variant="outline-primary" className="w-100">
                      Imprimer
                    </Button>
                  </Col>
                </Row>

                {renderTimeGrid()}
              </div>
            </Tab>

            <Tab eventKey="salles" title="Salles">
              <div className="pt-3">
                <SISDataTable
                  title="Gestion des salles"
                  data={salles}
                  columns={sallesColumns}
                  searchable
                  addButtonLabel="Ajouter une salle"
                />
              </div>
            </Tab>

            <Tab eventKey="reservations" title="Réservations">
              <div className="pt-3">
                <SISDataTable
                  title="Réservations de salles"
                  data={reservations}
                  columns={reservationsColumns}
                  searchable
                />
              </div>
            </Tab>
          </Tabs>
        </Card.Body>
      </Card>

      {/* Modal réservation */}
      <Modal
        title="Réserver une salle"
        isOpen={showReservation}
        onClose={() => setShowReservation(false)}
        size="lg"
      >
        <Form>
          <Form.Group>
            <Form.Label>Salle</Form.Label>
            <Form.Control as="select" name="salle">
              <option value="">Sélectionner...</option>
              {salles.filter(s => s.disponible).map((s) => (
                <option key={s.id} value={s.id}>{s.code} - {s.nom} ({s.capacite} places)</option>
              ))}
            </Form.Control>
          </Form.Group>
          <Row>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Date</Form.Label>
                <Form.Control type="date" name="date" />
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Heure début</Form.Label>
                <Form.Control type="time" name="heure_debut" />
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group>
                <Form.Label>Heure fin</Form.Label>
                <Form.Control type="time" name="heure_fin" />
              </Form.Group>
            </Col>
          </Row>
          <Form.Group>
            <Form.Label>Motif</Form.Label>
            <Form.Control as="select" name="motif">
              <option value="cours_rattrapage">Cours de rattrapage</option>
              <option value="examen">Examen</option>
              <option value="reunion">Réunion</option>
              <option value="soutenance">Soutenance</option>
              <option value="evenement">Événement</option>
              <option value="autre">Autre</option>
            </Form.Control>
          </Form.Group>
          <Form.Group>
            <Form.Label>Description</Form.Label>
            <Form.Control as="textarea" rows={3} name="description" />
          </Form.Group>
          <ActionRow>
            <Button variant="tertiary" onClick={() => setShowReservation(false)}>
              Annuler
            </Button>
            <Button type="submit">
              Réserver
            </Button>
          </ActionRow>
        </Form>
      </Modal>
    </div>
  );
};

export default EmploiDuTempsPage;
