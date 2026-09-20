import React, { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Row,
  Tab,
  Tabs,
} from '@openedx/paragon';
import { Save } from '@openedx/paragon/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common';
import {
  fetchApi,
  getCurrentEstablishmentUrl,
  patchApi,
} from '../../services/api';

const EMPTY_FORM = {
  fonctionnalites: {},
  configuration_visio: { provider: 'none', public_url: '' },
  configuration_academique: {},
};

const EtablissementPage = () => {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [academicJson, setAcademicJson] = useState('{}');
  const [academicError, setAcademicError] = useState('');
  const endpoint = getCurrentEstablishmentUrl();

  const {
    data: etablissement,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['etablissement-current'],
    queryFn: () => fetchApi(endpoint),
  });

  useEffect(() => {
    if (etablissement) {
      setFormData({
        ...etablissement,
        fonctionnalites: etablissement.fonctionnalites || {},
        configuration_visio: etablissement.configuration_visio || EMPTY_FORM.configuration_visio,
        configuration_academique: etablissement.configuration_academique || {},
      });
      setAcademicJson(JSON.stringify(etablissement.configuration_academique || {}, null, 2));
    }
  }, [etablissement]);

  const updateMutation = useMutation({
    mutationFn: (data) => patchApi(endpoint, data),
    onSuccess: (data) => {
      setFormData(data);
      queryClient.setQueryData(['etablissement-current'], data);
    },
  });

  const updateField = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
  };

  const updateFeature = (event) => {
    const { name, checked } = event.target;
    setFormData((current) => ({
      ...current,
      fonctionnalites: {
        ...current.fonctionnalites,
        [name]: checked,
      },
    }));
  };

  const updateLiveConfiguration = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({
      ...current,
      configuration_visio: {
        ...current.configuration_visio,
        [name]: value,
      },
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    let academicConfiguration;
    try {
      academicConfiguration = JSON.parse(academicJson);
      setAcademicError('');
    } catch (error) {
      setAcademicError('La configuration académique doit être un objet JSON valide.');
      return;
    }
    const {
      nom,
      type,
      type_personnalise: typePersonnalise,
      adresse,
      code_postal: codePostal,
      ville,
      pays,
      telephone,
      email,
      site_web: siteWeb,
      couleur_primaire: couleurPrimaire,
      couleur_secondaire: couleurSecondaire,
      fuseau_horaire: fuseauHoraire,
      fonctionnalites,
      configuration_visio: configurationVisio,
    } = formData;
    updateMutation.mutate({
      nom,
      type,
      type_personnalise: typePersonnalise,
      adresse,
      code_postal: codePostal,
      ville,
      pays,
      telephone,
      email,
      site_web: siteWeb,
      couleur_primaire: couleurPrimaire,
      couleur_secondaire: couleurSecondaire,
      fuseau_horaire: fuseauHoraire,
      fonctionnalites,
      configuration_visio: configurationVisio,
      configuration_academique: academicConfiguration,
    });
  };

  if (isLoading) {
    return <div>Chargement de la configuration...</div>;
  }

  if (isError) {
    return <Alert variant="danger">Impossible de charger la configuration de cet établissement.</Alert>;
  }

  return (
    <div>
      <PageHeader
        title="Configuration établissement"
        subtitle="Personnalisez l’identité, les modules pédagogiques et les services de votre organisation"
      />

      {updateMutation.isSuccess && (
        <Alert variant="success">La configuration a été enregistrée.</Alert>
      )}
      {updateMutation.isError && (
        <Alert variant="danger">L’enregistrement a échoué. Vérifiez les valeurs saisies.</Alert>
      )}

      <Form onSubmit={handleSubmit}>
        <Tabs defaultActiveKey="general">
          <Tab eventKey="general" title="Identité">
            <Card className="mt-3">
              <Card.Body>
                <Row>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Nom de l’établissement</Form.Label>
                      <Form.Control
                        name="nom"
                        value={formData.nom || ''}
                        onChange={updateField}
                        required
                      />
                    </Form.Group>
                  </Col>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Type d’établissement</Form.Label>
                      <Form.Control
                        as="select"
                        name="type"
                        value={formData.type || ''}
                        onChange={updateField}
                        required
                      >
                        {(formData.type_options || []).map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </Form.Control>
                    </Form.Group>
                  </Col>
                </Row>
                {formData.type === 'autre' && (
                  <Form.Group className="mb-3">
                    <Form.Label>Type personnalisé</Form.Label>
                    <Form.Control
                      name="type_personnalise"
                      value={formData.type_personnalise || ''}
                      onChange={updateField}
                      required
                    />
                  </Form.Group>
                )}
                <Form.Group className="mb-3">
                  <Form.Label>Adresse</Form.Label>
                  <Form.Control
                    name="adresse"
                    value={formData.adresse || ''}
                    onChange={updateField}
                  />
                </Form.Group>
                <Row>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Ville</Form.Label>
                      <Form.Control
                        name="ville"
                        value={formData.ville || ''}
                        onChange={updateField}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Code postal</Form.Label>
                      <Form.Control
                        name="code_postal"
                        value={formData.code_postal || ''}
                        onChange={updateField}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Pays</Form.Label>
                      <Form.Control
                        name="pays"
                        value={formData.pays || ''}
                        onChange={updateField}
                      />
                    </Form.Group>
                  </Col>
                </Row>
                <Row>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Téléphone</Form.Label>
                      <Form.Control
                        name="telephone"
                        value={formData.telephone || ''}
                        onChange={updateField}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Email</Form.Label>
                      <Form.Control
                        type="email"
                        name="email"
                        value={formData.email || ''}
                        onChange={updateField}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Site web</Form.Label>
                      <Form.Control
                        type="url"
                        name="site_web"
                        value={formData.site_web || ''}
                        onChange={updateField}
                      />
                    </Form.Group>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </Tab>

          <Tab eventKey="appearance" title="Apparence">
            <Card className="mt-3">
              <Card.Body>
                <Row>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Couleur principale</Form.Label>
                      <Form.Control
                        type="color"
                        name="couleur_primaire"
                        value={formData.couleur_primaire || '#0A3055'}
                        onChange={updateField}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Couleur secondaire</Form.Label>
                      <Form.Control
                        type="color"
                        name="couleur_secondaire"
                        value={formData.couleur_secondaire || '#FFFFFF'}
                        onChange={updateField}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4}>
                    <Form.Group className="mb-3">
                      <Form.Label>Fuseau horaire IANA</Form.Label>
                      <Form.Control
                        name="fuseau_horaire"
                        value={formData.fuseau_horaire || 'UTC'}
                        onChange={updateField}
                        placeholder="Africa/Abidjan"
                      />
                    </Form.Group>
                  </Col>
                </Row>
                <p className="text-muted mb-0">
                  Le logo est géré dans l’administration Django afin de conserver un téléversement sécurisé.
                </p>
              </Card.Body>
            </Card>
          </Tab>

          <Tab eventKey="features" title="Modules">
            <Card className="mt-3">
              <Card.Body>
                {(formData.feature_options || []).map((feature) => (
                  <Form.Check
                    key={feature.value}
                    className="mb-3"
                    type="switch"
                    id={`feature-${feature.value}`}
                    name={feature.value}
                    label={feature.label}
                    checked={Boolean(formData.fonctionnalites[feature.value])}
                    onChange={updateFeature}
                  />
                ))}
                <Alert variant="info" className="mb-0">
                  Les QCM et la correction automatique sont exécutés par le moteur Open edX ;
                  le SIS conserve la planification et les résultats consolidés.
                </Alert>
              </Card.Body>
            </Card>
          </Tab>

          <Tab eventKey="academic" title="Organisation académique">
            <Card className="mt-3">
              <Card.Body>
                <Form.Group>
                  <Form.Label>Configuration académique dynamique</Form.Label>
                  <Form.Control
                    as="textarea"
                    rows={18}
                    value={academicJson}
                    onChange={(event) => setAcademicJson(event.target.value)}
                    isInvalid={Boolean(academicError)}
                    spellCheck={false}
                  />
                  <Form.Control.Feedback type="invalid">
                    {academicError}
                  </Form.Control.Feedback>
                  <Form.Text>
                    Configurez l’échelle de notation, les types d’évaluation, les catalogues,
                    les dimensions de filtre et les rapports exportables. Le serveur valide
                    chaque code, champ et filtre avant l’enregistrement.
                  </Form.Text>
                </Form.Group>
              </Card.Body>
            </Card>
          </Tab>

          <Tab eventKey="live" title="Classes virtuelles">
            <Card className="mt-3">
              <Card.Body>
                <Row>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>Fournisseur</Form.Label>
                      <Form.Control
                        as="select"
                        name="provider"
                        value={formData.configuration_visio.provider || 'none'}
                        onChange={updateLiveConfiguration}
                      >
                        {(formData.live_provider_options || []).map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </Form.Control>
                    </Form.Group>
                  </Col>
                  <Col md={6}>
                    <Form.Group className="mb-3">
                      <Form.Label>URL publique HTTPS</Form.Label>
                      <Form.Control
                        type="url"
                        name="public_url"
                        value={formData.configuration_visio.public_url || ''}
                        onChange={updateLiveConfiguration}
                        placeholder="https://classes.example.edu"
                      />
                    </Form.Group>
                  </Col>
                </Row>
                <Alert variant="warning" className="mb-0">
                  Les clés et secrets BigBlueButton, Zoom ou LTI ne sont jamais saisis ici.
                  Ils doivent rester dans la configuration sécurisée du serveur Open edX.
                </Alert>
              </Card.Body>
            </Card>
          </Tab>
        </Tabs>

        <Button
          className="mt-3"
          type="submit"
          variant="primary"
          iconBefore={Save}
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? 'Enregistrement...' : 'Enregistrer la configuration'}
        </Button>
      </Form>
    </div>
  );
};

export default EtablissementPage;
