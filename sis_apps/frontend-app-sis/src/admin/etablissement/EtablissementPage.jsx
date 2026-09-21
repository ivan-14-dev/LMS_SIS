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

const normalizeAcademicConfiguration = (value = {}) => ({
  ...value,
  dimensions: value.dimensions || [],
  permission_groups: value.permission_groups || [],
  validation_policies: value.validation_policies || [],
  financial_workflows: value.financial_workflows || [],
  reports: value.reports || [],
});

const parseCsv = (value) => value.split(',').map((item) => item.trim()).filter(Boolean);
const formatCsv = (value) => (Array.isArray(value) ? value.join(', ') : '');

const parseObjectField = (value, label) => {
  if (!value.trim()) {
    return {};
  }
  const parsed = JSON.parse(value);
  if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
    throw new Error(`${label} doit être un objet JSON.`);
  }
  return parsed;
};

const parseArrayField = (value, label) => {
  if (!value.trim()) {
    return [];
  }
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} doit être une liste JSON.`);
  }
  return parsed;
};

const EtablissementPage = () => {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [academicConfiguration, setAcademicConfiguration] = useState(
    normalizeAcademicConfiguration({}),
  );
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
      const normalizedConfiguration = normalizeAcademicConfiguration(
        etablissement.configuration_academique || {},
      );
      setAcademicConfiguration(normalizedConfiguration);
      setAcademicJson(JSON.stringify(normalizedConfiguration, null, 2));
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

  const syncAcademicConfiguration = (nextConfiguration) => {
    setAcademicConfiguration(nextConfiguration);
    setAcademicJson(JSON.stringify(nextConfiguration, null, 2));
    setAcademicError('');
  };

  const updateAcademicSection = (section, updater) => {
    const currentItems = academicConfiguration[section] || [];
    const nextItems = updater(currentItems);
    syncAcademicConfiguration({
      ...academicConfiguration,
      [section]: nextItems,
    });
  };

  const updateAcademicJson = (event) => {
    const nextJson = event.target.value;
    setAcademicJson(nextJson);
    try {
      const parsed = normalizeAcademicConfiguration(JSON.parse(nextJson));
      setAcademicConfiguration(parsed);
      setAcademicError('');
    } catch (error) {
      setAcademicError('La configuration académique doit être un objet JSON valide.');
    }
  };

  const addAcademicItem = (section, template) => {
    updateAcademicSection(section, (items) => [...items, template]);
  };

  const removeAcademicItem = (section, index) => {
    updateAcademicSection(section, (items) => items.filter((_, currentIndex) => currentIndex !== index));
  };

  const updateAcademicItemField = (section, index, field, value) => {
    updateAcademicSection(section, (items) => items.map((item, currentIndex) => (
      currentIndex === index ? { ...item, [field]: value } : item
    )));
  };

  const updateAcademicJsonField = (section, index, field, rawValue, parser, label) => {
    try {
      updateAcademicItemField(section, index, field, parser(rawValue, label));
      setAcademicError('');
    } catch (error) {
      setAcademicError(error.message);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    let academicConfiguration;
    try {
      academicConfiguration = normalizeAcademicConfiguration(JSON.parse(academicJson));
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

  const configurationSchema = formData.configuration_schema || {};

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
            <Row className="mt-3">
              <Col xl={6} className="mb-3">
                <Card>
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <span>Dimensions dynamiques</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline-primary"
                      onClick={() => addAcademicItem('dimensions', {
                        code: '',
                        label: '',
                        axis: configurationSchema.dimension_axes?.[0]?.code || 'organizational',
                        scope: configurationSchema.dimension_scopes?.[0]?.code || 'tenant',
                        applicable_to: [],
                      })}
                    >
                      Ajouter
                    </Button>
                  </Card.Header>
                  <Card.Body>
                    {(academicConfiguration.dimensions || []).map((dimension, index) => (
                      <Card key={`dimension-${index}`} className="mb-3">
                        <Card.Body>
                          <Row>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Code</Form.Label>
                                <Form.Control
                                  value={dimension.code || ''}
                                  onChange={(event) => updateAcademicItemField('dimensions', index, 'code', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Libellé</Form.Label>
                                <Form.Control
                                  value={dimension.label || ''}
                                  onChange={(event) => updateAcademicItemField('dimensions', index, 'label', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                          </Row>
                          <Row>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Axe</Form.Label>
                                <Form.Control
                                  as="select"
                                  value={dimension.axis || ''}
                                  onChange={(event) => updateAcademicItemField('dimensions', index, 'axis', event.target.value)}
                                >
                                  {(configurationSchema.dimension_axes || []).map((option) => (
                                    <option key={option.code} value={option.code}>{option.label}</option>
                                  ))}
                                </Form.Control>
                              </Form.Group>
                            </Col>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Scope</Form.Label>
                                <Form.Control
                                  as="select"
                                  value={dimension.scope || ''}
                                  onChange={(event) => updateAcademicItemField('dimensions', index, 'scope', event.target.value)}
                                >
                                  {(configurationSchema.dimension_scopes || []).map((option) => (
                                    <option key={option.code} value={option.code}>{option.label}</option>
                                  ))}
                                </Form.Control>
                              </Form.Group>
                            </Col>
                          </Row>
                          <Form.Group className="mb-2">
                            <Form.Label>Applicable à</Form.Label>
                            <Form.Control
                              value={formatCsv(dimension.applicable_to)}
                              onChange={(event) => updateAcademicItemField('dimensions', index, 'applicable_to', parseCsv(event.target.value))}
                              placeholder="secondaire, superieur"
                            />
                          </Form.Group>
                          <Button type="button" variant="link" className="px-0" onClick={() => removeAcademicItem('dimensions', index)}>Supprimer</Button>
                        </Card.Body>
                      </Card>
                    ))}
                    {!academicConfiguration.dimensions?.length && (
                      <p className="text-muted mb-0">Aucune dimension personnalisée configurée.</p>
                    )}
                  </Card.Body>
                </Card>
              </Col>

              <Col xl={6} className="mb-3">
                <Card>
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <span>Groupes de permissions</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline-primary"
                      onClick={() => addAcademicItem('permission_groups', {
                        code: '',
                        label: '',
                        permissions: [],
                        attributes: {},
                      })}
                    >
                      Ajouter
                    </Button>
                  </Card.Header>
                  <Card.Body>
                    {(academicConfiguration.permission_groups || []).map((group, index) => (
                      <Card key={`group-${index}`} className="mb-3">
                        <Card.Body>
                          <Row>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Code</Form.Label>
                                <Form.Control
                                  value={group.code || ''}
                                  onChange={(event) => updateAcademicItemField('permission_groups', index, 'code', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Libellé</Form.Label>
                                <Form.Control
                                  value={group.label || ''}
                                  onChange={(event) => updateAcademicItemField('permission_groups', index, 'label', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                          </Row>
                          <Form.Group className="mb-2">
                            <Form.Label>Permissions</Form.Label>
                            <Form.Control
                              value={formatCsv(group.permissions)}
                              onChange={(event) => updateAcademicItemField('permission_groups', index, 'permissions', parseCsv(event.target.value))}
                              placeholder="notes.view_note, paiements.change_paiement"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Attributs (JSON)</Form.Label>
                            <Form.Control
                              as="textarea"
                              rows={4}
                              defaultValue={JSON.stringify(group.attributes || {}, null, 2)}
                              onBlur={(event) => updateAcademicJsonField('permission_groups', index, 'attributes', event.target.value, parseObjectField, 'Les attributs')}
                              spellCheck={false}
                            />
                          </Form.Group>
                          <Button type="button" variant="link" className="px-0" onClick={() => removeAcademicItem('permission_groups', index)}>Supprimer</Button>
                        </Card.Body>
                      </Card>
                    ))}
                  </Card.Body>
                </Card>
              </Col>
            </Row>

            <Row>
              <Col xl={6} className="mb-3">
                <Card>
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <span>Politiques de validation</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline-primary"
                      onClick={() => addAcademicItem('validation_policies', {
                        code: '',
                        label: '',
                        scope: configurationSchema.validation_scopes?.[0]?.code || 'tenant',
                        targets: {},
                        thresholds: {},
                        publication: {},
                      })}
                    >
                      Ajouter
                    </Button>
                  </Card.Header>
                  <Card.Body>
                    {(academicConfiguration.validation_policies || []).map((policy, index) => (
                      <Card key={`policy-${index}`} className="mb-3">
                        <Card.Body>
                          <Row>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Code</Form.Label>
                                <Form.Control
                                  value={policy.code || ''}
                                  onChange={(event) => updateAcademicItemField('validation_policies', index, 'code', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Libellé</Form.Label>
                                <Form.Control
                                  value={policy.label || ''}
                                  onChange={(event) => updateAcademicItemField('validation_policies', index, 'label', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                          </Row>
                          <Form.Group className="mb-2">
                            <Form.Label>Scope</Form.Label>
                            <Form.Control
                              as="select"
                              value={policy.scope || ''}
                              onChange={(event) => updateAcademicItemField('validation_policies', index, 'scope', event.target.value)}
                            >
                              {(configurationSchema.validation_scopes || []).map((option) => (
                                <option key={option.code} value={option.code}>{option.label}</option>
                              ))}
                            </Form.Control>
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Targets (JSON)</Form.Label>
                            <Form.Control
                              as="textarea"
                              rows={3}
                              defaultValue={JSON.stringify(policy.targets || {}, null, 2)}
                              onBlur={(event) => updateAcademicJsonField('validation_policies', index, 'targets', event.target.value, parseObjectField, 'Les targets')}
                              spellCheck={false}
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Seuils (JSON)</Form.Label>
                            <Form.Control
                              as="textarea"
                              rows={3}
                              defaultValue={JSON.stringify(policy.thresholds || {}, null, 2)}
                              onBlur={(event) => updateAcademicJsonField('validation_policies', index, 'thresholds', event.target.value, parseObjectField, 'Les seuils')}
                              spellCheck={false}
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Publication (JSON)</Form.Label>
                            <Form.Control
                              as="textarea"
                              rows={3}
                              defaultValue={JSON.stringify(policy.publication || {}, null, 2)}
                              onBlur={(event) => updateAcademicJsonField('validation_policies', index, 'publication', event.target.value, parseObjectField, 'La publication')}
                              spellCheck={false}
                            />
                          </Form.Group>
                          <Button type="button" variant="link" className="px-0" onClick={() => removeAcademicItem('validation_policies', index)}>Supprimer</Button>
                        </Card.Body>
                      </Card>
                    ))}
                  </Card.Body>
                </Card>
              </Col>

              <Col xl={6} className="mb-3">
                <Card>
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <span>Workflows financiers</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline-primary"
                      onClick={() => addAcademicItem('financial_workflows', {
                        code: '',
                        label: '',
                        scope: configurationSchema.financial_workflow_scopes?.[0]?.code || 'tenant',
                        required_permissions: [],
                        targets: {},
                        steps: [],
                        transitions: [],
                      })}
                    >
                      Ajouter
                    </Button>
                  </Card.Header>
                  <Card.Body>
                    {(academicConfiguration.financial_workflows || []).map((workflow, index) => (
                      <Card key={`workflow-${index}`} className="mb-3">
                        <Card.Body>
                          <Row>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Code</Form.Label>
                                <Form.Control
                                  value={workflow.code || ''}
                                  onChange={(event) => updateAcademicItemField('financial_workflows', index, 'code', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Libellé</Form.Label>
                                <Form.Control
                                  value={workflow.label || ''}
                                  onChange={(event) => updateAcademicItemField('financial_workflows', index, 'label', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                          </Row>
                          <Form.Group className="mb-2">
                            <Form.Label>Scope</Form.Label>
                            <Form.Control
                              as="select"
                              value={workflow.scope || ''}
                              onChange={(event) => updateAcademicItemField('financial_workflows', index, 'scope', event.target.value)}
                            >
                              {(configurationSchema.financial_workflow_scopes || []).map((option) => (
                                <option key={option.code} value={option.code}>{option.label}</option>
                              ))}
                            </Form.Control>
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Permissions requises</Form.Label>
                            <Form.Control
                              value={formatCsv(workflow.required_permissions)}
                              onChange={(event) => updateAcademicItemField('financial_workflows', index, 'required_permissions', parseCsv(event.target.value))}
                              placeholder="paiements.change_paiement"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Targets (JSON)</Form.Label>
                            <Form.Control
                              as="textarea"
                              rows={3}
                              defaultValue={JSON.stringify(workflow.targets || {}, null, 2)}
                              onBlur={(event) => updateAcademicJsonField('financial_workflows', index, 'targets', event.target.value, parseObjectField, 'Les targets')}
                              spellCheck={false}
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Étapes (JSON)</Form.Label>
                            <Form.Control
                              as="textarea"
                              rows={4}
                              defaultValue={JSON.stringify(workflow.steps || [], null, 2)}
                              onBlur={(event) => updateAcademicJsonField('financial_workflows', index, 'steps', event.target.value, parseArrayField, 'Les étapes')}
                              spellCheck={false}
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Transitions (JSON)</Form.Label>
                            <Form.Control
                              as="textarea"
                              rows={4}
                              defaultValue={JSON.stringify(workflow.transitions || [], null, 2)}
                              onBlur={(event) => updateAcademicJsonField('financial_workflows', index, 'transitions', event.target.value, parseArrayField, 'Les transitions')}
                              spellCheck={false}
                            />
                          </Form.Group>
                          <Button type="button" variant="link" className="px-0" onClick={() => removeAcademicItem('financial_workflows', index)}>Supprimer</Button>
                        </Card.Body>
                      </Card>
                    ))}
                  </Card.Body>
                </Card>
              </Col>
            </Row>

            <Row>
              <Col xl={6} className="mb-3">
                <Card>
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <span>Rapports dynamiques</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline-primary"
                      onClick={() => addAcademicItem('reports', {
                        code: '',
                        label: '',
                        dataset: configurationSchema.report_datasets?.[0]?.code || '',
                        fields: [],
                        allowed_filters: [],
                        required_permissions: [],
                        default_group_by: '',
                      })}
                    >
                      Ajouter
                    </Button>
                  </Card.Header>
                  <Card.Body>
                    {(academicConfiguration.reports || []).map((report, index) => (
                      <Card key={`report-${index}`} className="mb-3">
                        <Card.Body>
                          <Row>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Code</Form.Label>
                                <Form.Control
                                  value={report.code || ''}
                                  onChange={(event) => updateAcademicItemField('reports', index, 'code', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Libellé</Form.Label>
                                <Form.Control
                                  value={report.label || ''}
                                  onChange={(event) => updateAcademicItemField('reports', index, 'label', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                          </Row>
                          <Form.Group className="mb-2">
                            <Form.Label>Dataset</Form.Label>
                            <Form.Control
                              as="select"
                              value={report.dataset || ''}
                              onChange={(event) => updateAcademicItemField('reports', index, 'dataset', event.target.value)}
                            >
                              {(configurationSchema.report_datasets || []).map((option) => (
                                <option key={option.code} value={option.code}>{option.label}</option>
                              ))}
                            </Form.Control>
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Champs</Form.Label>
                            <Form.Control
                              value={formatCsv(report.fields)}
                              onChange={(event) => updateAcademicItemField('reports', index, 'fields', parseCsv(event.target.value))}
                              placeholder="numero, montant, statut"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Filtres autorisés</Form.Label>
                            <Form.Control
                              value={formatCsv(report.allowed_filters)}
                              onChange={(event) => updateAcademicItemField('reports', index, 'allowed_filters', parseCsv(event.target.value))}
                              placeholder="annee, formation, statut"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Permissions requises</Form.Label>
                            <Form.Control
                              value={formatCsv(report.required_permissions)}
                              onChange={(event) => updateAcademicItemField('reports', index, 'required_permissions', parseCsv(event.target.value))}
                              placeholder="paiements.view_paiementfrais"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Groupement par défaut</Form.Label>
                            <Form.Control
                              value={report.default_group_by || ''}
                              onChange={(event) => updateAcademicItemField('reports', index, 'default_group_by', event.target.value)}
                            />
                          </Form.Group>
                          <Button type="button" variant="link" className="px-0" onClick={() => removeAcademicItem('reports', index)}>Supprimer</Button>
                        </Card.Body>
                      </Card>
                    ))}
                  </Card.Body>
                </Card>
              </Col>

              <Col xl={6} className="mb-3">
                <Card>
                  <Card.Header>Mode avancé JSON</Card.Header>
                  <Card.Body>
                    <Form.Group>
                      <Form.Label>Configuration académique complète</Form.Label>
                      <Form.Control
                        as="textarea"
                        rows={24}
                        value={academicJson}
                        onChange={updateAcademicJson}
                        isInvalid={Boolean(academicError)}
                        spellCheck={false}
                      />
                      <Form.Control.Feedback type="invalid">
                        {academicError}
                      </Form.Control.Feedback>
                      <Form.Text>
                        Utilisez les formulaires ci-dessus pour les sections principales et le JSON
                        avancé pour les catalogues, l’échelle de notation et les cas spécifiques.
                        Le serveur valide toujours la configuration complète avant enregistrement.
                      </Form.Text>
                    </Form.Group>
                  </Card.Body>
                </Card>
              </Col>
            </Row>
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
