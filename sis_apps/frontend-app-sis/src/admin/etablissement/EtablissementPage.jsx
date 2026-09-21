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
import {
  formatCsv,
  normalizeAcademicConfiguration,
  parseArrayField,
  parseCsv,
  parseObjectField,
  stringifyAcademicConfiguration,
} from './academicConfigurationForm';

const EMPTY_FORM = {
  fonctionnalites: {},
  configuration_visio: { provider: 'none', public_url: '' },
  configuration_academique: {},
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
      setAcademicJson(stringifyAcademicConfiguration(normalizedConfiguration));
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
    setAcademicJson(stringifyAcademicConfiguration(nextConfiguration));
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

  const updateSubmissionWindowField = (windowType, field, value) => {
    syncAcademicConfiguration({
      ...academicConfiguration,
      submission_windows: {
        ...(academicConfiguration.submission_windows || {}),
        [windowType]: {
          ...((academicConfiguration.submission_windows || {})[windowType] || {}),
          [field]: value,
        },
      },
    });
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    let parsedAcademicConfiguration;
    try {
      parsedAcademicConfiguration = normalizeAcademicConfiguration(JSON.parse(academicJson));
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
      configuration_academique: parsedAcademicConfiguration,
    });
  };

  if (isLoading) {
    return <div>Chargement de la configuration...</div>;
  }

  if (isError) {
    return <Alert variant="danger">Impossible de charger la configuration de cet établissement.</Alert>;
  }

  const configurationSchema = formData.configuration_schema || {};
  const reportDatasets = configurationSchema.report_datasets || [];
  const submissionRecipientRoleOptions = configurationSchema.submission_window_recipient_roles || [];
  const submissionTemplateVariables = configurationSchema.submission_window_template_variables || [];
  const submissionSeverityOptions = configurationSchema.submission_window_severities || [];
  const submissionChannelOptions = configurationSchema.submission_window_notification_channels || [];
  const getReportDatasetDefinition = (datasetCode) => (
    reportDatasets.find((dataset) => dataset.code === datasetCode) || null
  );

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
                      <Card key={dimension.code || dimension.label || JSON.stringify(dimension)} className="mb-3">
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
                      <Card key={group.code || group.label || JSON.stringify(group)} className="mb-3">
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
                  <Card.Header>Fenêtres globales de soumission</Card.Header>
                  <Card.Body>
                    {(configurationSchema.submission_window_types || []).map((windowType) => {
                      const settings = (academicConfiguration.submission_windows || {})[windowType.code] || {};
                      return (
                        <Card key={windowType.code} className="mb-3">
                          <Card.Body>
                            <div className="d-flex justify-content-between align-items-center mb-3">
                              <strong>{windowType.label}</strong>
                              <Form.Check
                                type="switch"
                                id={`submission-window-enabled-${windowType.code}`}
                                label="Actif"
                                checked={Boolean(settings.enabled)}
                                onChange={(event) => updateSubmissionWindowField(windowType.code, 'enabled', event.target.checked)}
                              />
                            </div>
                            <Row>
                              <Col md={6}>
                                <Form.Group className="mb-2">
                                  <Form.Label>Décalage ouverture (heures)</Form.Label>
                                  <Form.Control
                                    type="number"
                                    value={settings.default_open_offset_hours ?? 0}
                                    onChange={(event) => updateSubmissionWindowField(windowType.code, 'default_open_offset_hours', Number(event.target.value || 0))}
                                  />
                                </Form.Group>
                              </Col>
                              <Col md={6}>
                                <Form.Group className="mb-2">
                                  <Form.Label>Décalage fermeture (heures)</Form.Label>
                                  <Form.Control
                                    type="number"
                                    value={settings.default_close_offset_hours ?? 0}
                                    onChange={(event) => updateSubmissionWindowField(windowType.code, 'default_close_offset_hours', Number(event.target.value || 0))}
                                  />
                                </Form.Group>
                              </Col>
                            </Row>
                            <Form.Group className="mb-0">
                              <Form.Label>Alertes avant fermeture (heures)</Form.Label>
                              <Form.Control
                                value={formatCsv(settings.reminder_hours)}
                                onChange={(event) => updateSubmissionWindowField(windowType.code, 'reminder_hours', parseCsv(event.target.value).map((item) => Number(item)).filter((item) => !Number.isNaN(item) && item >= 0))}
                                placeholder="24, 2"
                              />
                            </Form.Group>
                            <Form.Check
                              className="mt-3"
                              type="switch"
                              id={`submission-window-assigned-${windowType.code}`}
                              label="Notifier aussi les responsables directement affectés"
                              checked={settings.notify_assigned_users ?? true}
                              onChange={(event) => updateSubmissionWindowField(windowType.code, 'notify_assigned_users', event.target.checked)}
                            />
                            <Row className="mt-3">
                              <Col md={6}>
                                <Form.Group className="mb-2">
                                  <Form.Label>Rôles à notifier</Form.Label>
                                  <Form.Select
                                    multiple
                                    value={settings.recipient_role_codes || []}
                                    onChange={(event) => updateSubmissionWindowField(
                                      windowType.code,
                                      'recipient_role_codes',
                                      Array.from(event.target.selectedOptions, (option) => option.value),
                                    )}
                                  >
                                    {submissionRecipientRoleOptions.map((option) => (
                                      <option key={option.code} value={option.code}>{option.label}</option>
                                    ))}
                                  </Form.Select>
                                  <Form.Text muted>
                                    Maintenez Ctrl/Cmd pour sélectionner plusieurs rôles.
                                  </Form.Text>
                                </Form.Group>
                              </Col>
                              <Col md={6}>
                                <Form.Group className="mb-0">
                                  <Form.Label>Groupes dynamiques à notifier</Form.Label>
                                  <Form.Select
                                    multiple
                                    value={settings.recipient_group_codes || []}
                                    onChange={(event) => updateSubmissionWindowField(
                                      windowType.code,
                                      'recipient_group_codes',
                                      Array.from(event.target.selectedOptions, (option) => option.value),
                                    )}
                                  >
                                    {(academicConfiguration.permission_groups || []).map((group) => (
                                      <option key={group.code} value={group.code}>{group.label || group.code}</option>
                                    ))}
                                  </Form.Select>
                                  <Form.Text muted>
                                    Les groupes proviennent de la section « Groupes de permissions dynamiques ».
                                  </Form.Text>
                                </Form.Group>
                              </Col>
                            </Row>
                            <Row className="mt-3">
                              <Col md={6}>
                                <Form.Group className="mb-2">
                                  <Form.Label>Titre de notification</Form.Label>
                                  <Form.Control
                                    value={settings.title_template || ''}
                                    onChange={(event) => updateSubmissionWindowField(windowType.code, 'title_template', event.target.value)}
                                    placeholder="Clôture de soumission imminente"
                                  />
                                </Form.Group>
                              </Col>
                              <Col md={6}>
                                <Form.Group className="mb-0">
                                  <Form.Label>Message de notification</Form.Label>
                                  <Form.Control
                                    as="textarea"
                                    rows={3}
                                    value={settings.message_template || ''}
                                    onChange={(event) => updateSubmissionWindowField(windowType.code, 'message_template', event.target.value)}
                                    placeholder="Clôture de la {window_label} de {object_label} dans moins de {threshold_hours}h."
                                  />
                                </Form.Group>
                              </Col>
                            </Row>
                            <Form.Text muted className="d-block mt-2">
                              Variables disponibles : {submissionTemplateVariables.map((item) => `{${item.code}}`).join(', ')}
                            </Form.Text>
                            <Row className="mt-3">
                              <Col md={6}>
                                <Form.Group className="mb-2">
                                  <Form.Label>Catégorie de notification</Form.Label>
                                  <Form.Control
                                    value={settings.notification_category || ''}
                                    onChange={(event) => updateSubmissionWindowField(windowType.code, 'notification_category', event.target.value)}
                                    placeholder="submission_deadline"
                                  />
                                </Form.Group>
                              </Col>
                              <Col md={6}>
                                <Form.Group className="mb-0">
                                  <Form.Label>Sévérité</Form.Label>
                                  <Form.Select
                                    value={settings.notification_severity || 'warning'}
                                    onChange={(event) => updateSubmissionWindowField(windowType.code, 'notification_severity', event.target.value)}
                                  >
                                    {submissionSeverityOptions.map((option) => (
                                      <option key={option.code} value={option.code}>{option.label}</option>
                                    ))}
                                  </Form.Select>
                                </Form.Group>
                              </Col>
                            </Row>
                            <Form.Group className="mt-3 mb-0">
                              <Form.Label>Canaux de notification</Form.Label>
                              <Form.Select
                                multiple
                                value={settings.notification_channels || []}
                                onChange={(event) => updateSubmissionWindowField(
                                  windowType.code,
                                  'notification_channels',
                                  Array.from(event.target.selectedOptions, (option) => option.value),
                                )}
                              >
                                {submissionChannelOptions.map((option) => (
                                  <option key={option.code} value={option.code}>{option.label}</option>
                                ))}
                              </Form.Select>
                              <Form.Text muted>
                                Le centre de notifications reste alimenté, et les canaux email/SMS/webhook déclenchent aussi des diffusions externes lorsqu'ils sont configurés.
                              </Form.Text>
                            </Form.Group>
                            <Row className="mt-3">
                              <Col md={6}>
                                <Form.Group className="mb-2">
                                  <Form.Label>Passerelle SMS (URL)</Form.Label>
                                  <Form.Control
                                    value={settings.sms_gateway_url || ''}
                                    onChange={(event) => updateSubmissionWindowField(windowType.code, 'sms_gateway_url', event.target.value)}
                                    placeholder="https://sms.example.com/send"
                                  />
                                  <Form.Text muted>
                                    Utilisée quand le canal SMS est activé et que le destinataire a un téléphone.
                                  </Form.Text>
                                </Form.Group>
                              </Col>
                              <Col md={6}>
                                <Form.Group className="mb-0">
                                  <Form.Label>Webhooks de diffusion</Form.Label>
                                  <Form.Control
                                    value={formatCsv(settings.webhook_urls)}
                                    onChange={(event) => updateSubmissionWindowField(windowType.code, 'webhook_urls', parseCsv(event.target.value))}
                                    placeholder="https://example.com/hook-1, https://example.com/hook-2"
                                  />
                                  <Form.Text muted>
                                    Les emails utilisent les adresses des destinataires ; les webhooks sont appelés une fois par événement.
                                  </Form.Text>
                                </Form.Group>
                              </Col>
                            </Row>
                          </Card.Body>
                        </Card>
                      );
                    })}
                    <Alert variant="info" className="mb-0">
                      Les décalages sont appliqués automatiquement si une évaluation ou une épreuve ne définit pas ses propres dates de soumission.
                    </Alert>
                  </Card.Body>
                </Card>
              </Col>

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
                      <Card key={policy.code || policy.label || JSON.stringify(policy)} className="mb-3">
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
                      <Card key={workflow.code || workflow.label || JSON.stringify(workflow)} className="mb-3">
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
                        formats: ['csv'],
                        allowed_filters: [],
                        required_permissions: [],
                        default_group_by: '',
                      })}
                    >
                      Ajouter
                    </Button>
                  </Card.Header>
                  <Card.Body>
                    {(academicConfiguration.reports || []).map((report, index) => {
                      const datasetDefinition = getReportDatasetDefinition(report.dataset);
                      return (
                        <Card key={report.code || report.label || JSON.stringify(report)} className="mb-3">
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
                              {datasetDefinition && (
                                <Form.Text>
                                  Champs disponibles : {datasetDefinition.fields.map((field) => field.code).join(', ') || 'aucun'}.
                                  {' '}
                                  Filtres : {datasetDefinition.allowed_filters.map((filter) => filter.code).join(', ') || 'aucun'}.
                                  {' '}
                                  Groupements : {datasetDefinition.group_by_options.map((group) => group.code).join(', ') || 'aucun'}.
                                </Form.Text>
                              )}
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
                              <Form.Label>Formats autorisés</Form.Label>
                              <Form.Control
                                value={formatCsv(report.formats)}
                                onChange={(event) => updateAcademicItemField('reports', index, 'formats', parseCsv(event.target.value))}
                                placeholder="csv, xlsx, pdf"
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
                      );
                    })}
                  </Card.Body>
                </Card>

                <Card className="mt-3">
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <span>Modèles d’import Excel</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline-primary"
                      onClick={() => addAcademicItem('import_templates', {
                        code: '',
                        label: '',
                        type: configurationSchema.import_template_types?.[0]?.code || '',
                        allowed_extensions: ['xlsx', 'xls'],
                        columns: [],
                        strict_columns: true,
                      })}
                    >
                      Ajouter
                    </Button>
                  </Card.Header>
                  <Card.Body>
                    {(academicConfiguration.import_templates || []).map((template, index) => (
                      <Card key={template.code || template.label || JSON.stringify(template)} className="mb-3">
                        <Card.Body>
                          <Row>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Code</Form.Label>
                                <Form.Control
                                  value={template.code || ''}
                                  onChange={(event) => updateAcademicItemField('import_templates', index, 'code', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Libellé</Form.Label>
                                <Form.Control
                                  value={template.label || ''}
                                  onChange={(event) => updateAcademicItemField('import_templates', index, 'label', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                          </Row>
                          <Form.Group className="mb-2">
                            <Form.Label>Type</Form.Label>
                            <Form.Control
                              as="select"
                              value={template.type || ''}
                              onChange={(event) => updateAcademicItemField('import_templates', index, 'type', event.target.value)}
                            >
                              {(configurationSchema.import_template_types || []).map((option) => (
                                <option key={option.code} value={option.code}>{option.label}</option>
                              ))}
                            </Form.Control>
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Extensions autorisées</Form.Label>
                            <Form.Control
                              value={formatCsv(template.allowed_extensions)}
                              onChange={(event) => updateAcademicItemField('import_templates', index, 'allowed_extensions', parseCsv(event.target.value))}
                              placeholder="xlsx, xls"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Colonnes strictes</Form.Label>
                            <Form.Control
                              value={formatCsv(template.columns)}
                              onChange={(event) => updateAcademicItemField('import_templates', index, 'columns', parseCsv(event.target.value))}
                              placeholder="epreuve_id, eleve_matricule, note"
                            />
                          </Form.Group>
                          <Form.Check
                            type="switch"
                            id={`import-template-strict-${index}`}
                            label="Refuser les colonnes inattendues"
                            checked={Boolean(template.strict_columns)}
                            onChange={(event) => updateAcademicItemField('import_templates', index, 'strict_columns', event.target.checked)}
                          />
                          <Button type="button" variant="link" className="px-0" onClick={() => removeAcademicItem('import_templates', index)}>Supprimer</Button>
                        </Card.Body>
                      </Card>
                    ))}
                  </Card.Body>
                </Card>

                <Card className="mt-3">
                  <Card.Header className="d-flex justify-content-between align-items-center">
                    <span>Workflow résultats d’examen</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline-primary"
                      onClick={() => addAcademicItem('exam_result_workflows', {
                        code: '',
                        label: '',
                        scope: configurationSchema.exam_result_workflow_scopes?.[0]?.code || 'tenant',
                        variants: ['secondaire'],
                        verification_group_codes: [],
                        validation_group_codes: [],
                        publication_group_codes: [],
                        allowed_export_formats: ['csv', 'xlsx', 'pdf'],
                        import_template_codes: [],
                        correction_window_days: 0,
                        allow_retake_after_closure: true,
                        allow_student_submission: false,
                      })}
                    >
                      Ajouter
                    </Button>
                  </Card.Header>
                  <Card.Body>
                    {(academicConfiguration.exam_result_workflows || []).map((workflow, index) => (
                      <Card key={workflow.code || workflow.label || JSON.stringify(workflow)} className="mb-3">
                        <Card.Body>
                          <Row>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Code</Form.Label>
                                <Form.Control
                                  value={workflow.code || ''}
                                  onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'code', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                            <Col md={6}>
                              <Form.Group className="mb-2">
                                <Form.Label>Libellé</Form.Label>
                                <Form.Control
                                  value={workflow.label || ''}
                                  onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'label', event.target.value)}
                                />
                              </Form.Group>
                            </Col>
                          </Row>
                          <Form.Group className="mb-2">
                            <Form.Label>Portée</Form.Label>
                            <Form.Control
                              as="select"
                              value={workflow.scope || 'tenant'}
                              onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'scope', event.target.value)}
                            >
                              {(configurationSchema.exam_result_workflow_scopes || []).map((option) => (
                                <option key={option.code} value={option.code}>{option.label}</option>
                              ))}
                            </Form.Control>
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Variantes</Form.Label>
                            <Form.Control
                              value={formatCsv(workflow.variants)}
                              onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'variants', parseCsv(event.target.value))}
                              placeholder="secondaire, superieur"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Groupes de vérification</Form.Label>
                            <Form.Control
                              value={formatCsv(workflow.verification_group_codes)}
                              onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'verification_group_codes', parseCsv(event.target.value))}
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Groupes de validation</Form.Label>
                            <Form.Control
                              value={formatCsv(workflow.validation_group_codes)}
                              onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'validation_group_codes', parseCsv(event.target.value))}
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Groupes de publication</Form.Label>
                            <Form.Control
                              value={formatCsv(workflow.publication_group_codes)}
                              onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'publication_group_codes', parseCsv(event.target.value))}
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Formats d’export</Form.Label>
                            <Form.Control
                              value={formatCsv(workflow.allowed_export_formats)}
                              onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'allowed_export_formats', parseCsv(event.target.value))}
                              placeholder="csv, xlsx, pdf"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Modèles d’import</Form.Label>
                            <Form.Control
                              value={formatCsv(workflow.import_template_codes)}
                              onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'import_template_codes', parseCsv(event.target.value))}
                              placeholder="exam_grades, final_results"
                            />
                          </Form.Group>
                          <Form.Group className="mb-2">
                            <Form.Label>Fenêtre de correction après réouverture (jours)</Form.Label>
                            <Form.Control
                              type="number"
                              min="0"
                              value={workflow.correction_window_days ?? 0}
                              onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'correction_window_days', Number(event.target.value || 0))}
                            />
                          </Form.Group>
                          <Form.Check
                            type="switch"
                            id={`exam-result-retake-${index}`}
                            className="mb-2"
                            label="Autoriser les rattrapages après clôture"
                            checked={Boolean(workflow.allow_retake_after_closure)}
                            onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'allow_retake_after_closure', event.target.checked)}
                          />
                          <Form.Check
                            type="switch"
                            id={`exam-result-submission-${index}`}
                            label="Autoriser le dépôt étudiant"
                            checked={Boolean(workflow.allow_student_submission)}
                            onChange={(event) => updateAcademicItemField('exam_result_workflows', index, 'allow_student_submission', event.target.checked)}
                          />
                          <Button type="button" variant="link" className="px-0" onClick={() => removeAcademicItem('exam_result_workflows', index)}>Supprimer</Button>
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
