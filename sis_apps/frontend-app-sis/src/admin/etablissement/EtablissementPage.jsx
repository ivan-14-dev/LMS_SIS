import React from 'react';
import { Row, Col, Card, Form, Button, Tabs, Tab } from '@openedx/paragon';
import { Save, Business } from '@openedx/paragon/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PageHeader, StatCard } from '../../components/common';
import { fetchApi, getAdminApiUrl } from '../../services/api';

const EtablissementPage = () => {
  const queryClient = useQueryClient();
  
  const { data: etablissement, isLoading } = useQuery({
    queryKey: ['etablissement'],
    queryFn: () => fetchApi(`${getAdminApiUrl()}/etablissement/`),
  });

  const updateMutation = useMutation({
    mutationFn: (data) => fetchApi(`${getAdminApiUrl()}/etablissement/`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
    onSuccess: () => queryClient.invalidateQueries(['etablissement']),
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    updateMutation.mutate(data);
  };

  if (isLoading) return <div>Chargement...</div>;

  return (
    <div>
      <PageHeader
        title="Configuration établissement"
        subtitle="Paramètres généraux de l'établissement"
      />

      <Tabs defaultActiveKey="general">
        <Tab eventKey="general" title="Informations générales">
          <Card className="mt-3">
            <Card.Body>
              <Form onSubmit={handleSubmit}>
                <Row>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Nom de l'établissement</Form.Label>
                      <Form.Control name="nom" defaultValue={etablissement?.nom} required />
                    </Form.Group>
                  </Col>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Code établissement</Form.Label>
                      <Form.Control name="code" defaultValue={etablissement?.code} required />
                    </Form.Group>
                  </Col>
                </Row>
                <Row>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Type d'établissement</Form.Label>
                      <Form.Control as="select" name="type" defaultValue={etablissement?.type}>
                        <option value="universite">Université</option>
                        <option value="ecole_superieure">École supérieure</option>
                        <option value="institut">Institut</option>
                        <option value="lycee">Lycée</option>
                        <option value="college">Collège</option>
                      </Form.Control>
                    </Form.Group>
                  </Col>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Statut</Form.Label>
                      <Form.Control as="select" name="statut" defaultValue={etablissement?.statut}>
                        <option value="public">Public</option>
                        <option value="prive">Privé</option>
                      </Form.Control>
                    </Form.Group>
                  </Col>
                </Row>
                <Row>
                  <Col md={12}>
                    <Form.Group className="mb-3">
                      <Form.Label>Adresse</Form.Label>
                      <Form.Control name="adresse" defaultValue={etablissement?.adresse} />
                    </Form.Group>
                  </Col>
                </Row>
                <Row>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Ville</Form.Label>
                      <Form.Control name="ville" defaultValue={etablissement?.ville} />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Code postal</Form.Label>
                      <Form.Control name="code_postal" defaultValue={etablissement?.code_postal} />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Pays</Form.Label>
                      <Form.Control name="pays" defaultValue={etablissement?.pays || 'France'} />
                    </Form.Group>
                  </Col>
                </Row>
                <Row>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Téléphone</Form.Label>
                      <Form.Control name="telephone" defaultValue={etablissement?.telephone} />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Email</Form.Label>
                      <Form.Control type="email" name="email" defaultValue={etablissement?.email} />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Site web</Form.Label>
                      <Form.Control name="site_web" defaultValue={etablissement?.site_web} />
                    </Form.Group>
                  </Col>
                </Row>
                <Button type="submit" variant="primary" iconBefore={Save} disabled={updateMutation.isLoading}>
                  {updateMutation.isLoading ? 'Enregistrement...' : 'Enregistrer'}
                </Button>
              </Form>
            </Card.Body>
          </Card>
        </Tab>

        <Tab eventKey="annee" title="Année scolaire">
          <Card className="mt-3">
            <Card.Body>
              <Row>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Année scolaire en cours</Form.Label>
                    <Form.Control defaultValue={etablissement?.annee_scolaire || '2025-2026'} />
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group className="mb-3">
                    <Form.Label>Trimestre/Semestre actif</Form.Label>
                    <Form.Control as="select" defaultValue="1">
                      <option value="1">Trimestre 1 / Semestre 1</option>
                      <option value="2">Trimestre 2</option>
                      <option value="3">Trimestre 3 / Semestre 2</option>
                    </Form.Control>
                  </Form.Group>
                </Col>
              </Row>
              <Button variant="primary" iconBefore={Save}>Enregistrer</Button>
            </Card.Body>
          </Card>
        </Tab>

        <Tab eventKey="logo" title="Logo & Apparence">
          <Card className="mt-3">
            <Card.Body>
              <Form.Group className="mb-3">
                <Form.Label>Logo de l'établissement</Form.Label>
                <Form.Control type="file" accept="image/*" />
              </Form.Group>
              <Form.Group className="mb-3">
                <Form.Label>Couleur principale</Form.Label>
                <Form.Control type="color" defaultValue="#0066CC" />
              </Form.Group>
              <Button variant="primary" iconBefore={Save}>Enregistrer</Button>
            </Card.Body>
          </Card>
        </Tab>
      </Tabs>
    </div>
  );
};

export default EtablissementPage;
