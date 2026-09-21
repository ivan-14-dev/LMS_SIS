import React, { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Row, Col, Card, Badge, Tabs, Tab } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import {
  useAjouterMatiereIndividuelleEleve,
  useEleveDetail,
  useEleveMatieresIndividuelles,
  useNotesByEleve,
  usePresencesByEleve,
  useRetirerMatiereIndividuelleEleve,
  useSecondaireMatieres,
} from '../../services/api';

const emptyForm = {
  matiere: '',
  commentaire: '',
  obligatoire: true,
};

const EleveDetailPage = () => {
  const { id } = useParams();
  const [formData, setFormData] = useState(emptyForm);
  const { data: eleve, isLoading } = useEleveDetail(id);
  const { data: notes = [] } = useNotesByEleve(id);
  const { data: presences = [] } = usePresencesByEleve(id);
  const { data: matieres = [] } = useSecondaireMatieres();
  const { data: matieresIndividuelles = [] } = useEleveMatieresIndividuelles(id);
  const ajouterMatiere = useAjouterMatiereIndividuelleEleve();
  const retirerMatiere = useRetirerMatiereIndividuelleEleve();

  const notesColumns = [
    { Header: 'Évaluation', accessor: 'evaluation_titre' },
    { Header: 'Élève', accessor: 'eleve_nom' },
    {
      Header: 'Note',
      accessor: 'valeur',
      Cell: ({ value }) => (value !== undefined && value !== null ? `${value}/20` : '-'),
    },
    { Header: 'Statut', accessor: 'statut_display' },
  ];

  const presencesColumns = [
    { Header: 'Date', accessor: 'date' },
    { Header: 'Matière', accessor: 'matiere_nom' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => (
        <Badge variant={value === 'present' ? 'success' : value === 'absent' ? 'danger' : 'warning'}>
          {value}
        </Badge>
      ),
    },
    { Header: 'Justification', accessor: 'justification' },
  ];

  const individualColumns = [
    { Header: 'Matière', accessor: 'matiere_nom' },
    { Header: 'Code', accessor: 'matiere_code' },
    { Header: 'Coefficient', accessor: 'coefficient' },
    { Header: 'Crédits', accessor: 'credits' },
    {
      Header: 'Type',
      accessor: 'obligatoire',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'light'}>{value ? 'Obligatoire' : 'Optionnelle'}</Badge>
      ),
    },
  ];

  const matiereOptions = useMemo(
    () => (Array.isArray(matieres) ? matieres.filter((matiere) => matiere?.id && matiere?.nom) : []),
    [matieres],
  );

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!formData.matiere) {
      return;
    }
    await ajouterMatiere.mutateAsync({
      eleveId: id,
      data: {
        matiere: Number(formData.matiere),
        obligatoire: formData.obligatoire,
        commentaire: formData.commentaire,
      },
    });
    setFormData(emptyForm);
  };

  const handleRemove = async (affectationId) => {
    await retirerMatiere.mutateAsync({ eleveId: id, affectationId });
  };

  if (isLoading) return <div>Chargement...</div>;
  if (!eleve) return <div>Élève non trouvé</div>;

  return (
    <div>
      <PageHeader
        title={eleve.full_name}
        subtitle={`Matricule: ${eleve.matricule}`}
        breadcrumbs={[
          { label: 'Élèves', href: '/secondaire/eleves' },
          { label: eleve.full_name },
        ]}
      />

      <Row className="mb-4">
        <Col md={4}>
          <Card>
            <Card.Header><Card.Title>Informations personnelles</Card.Title></Card.Header>
            <Card.Body>
              <dl>
                <dt>Matricule</dt><dd>{eleve.matricule}</dd>
                <dt>Date de naissance</dt><dd>{eleve.date_naissance}</dd>
                <dt>Lieu de naissance</dt><dd>{eleve.lieu_naissance}</dd>
                <dt>Sexe</dt><dd>{eleve.sexe_display}</dd>
                <dt>Classe</dt><dd>{eleve.classe_nom || 'Non affecté'}</dd>
                <dt>Statut</dt>
                <dd>
                  <Badge variant={eleve.statut === 'actif' ? 'success' : 'danger'}>
                    {eleve.statut_display}
                  </Badge>
                </dd>
              </dl>
            </Card.Body>
          </Card>
        </Col>
        <Col md={8}>
          <Card>
            <Card.Body>
              <Tabs defaultActiveKey="notes">
                <Tab eventKey="notes" title="Notes">
                  <div className="pt-3">
                    <SISDataTable title="" data={notes} columns={notesColumns} searchable={false} exportable />
                  </div>
                </Tab>
                <Tab eventKey="presences" title="Présences">
                  <div className="pt-3">
                    <SISDataTable title="" data={presences} columns={presencesColumns} searchable={false} exportable />
                  </div>
                </Tab>
                <Tab eventKey="matieres-individuelles" title="Matières individualisées">
                  <div className="pt-3">
                    <form onSubmit={handleSubmit} className="mb-4">
                      <div className="mb-3">
                        <label htmlFor="matiere-individuelle" className="form-label">Matière</label>
                        <select
                          id="matiere-individuelle"
                          className="form-select"
                          value={formData.matiere}
                          onChange={(event) => setFormData((current) => ({ ...current, matiere: event.target.value }))}
                        >
                          <option value="">Sélectionner une matière</option>
                          {matiereOptions.map((matiere) => (
                            <option key={matiere.id} value={matiere.id}>
                              {matiere.nom}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="form-check mb-3">
                        <input
                          id="obligatoire-individuelle"
                          className="form-check-input"
                          type="checkbox"
                          checked={formData.obligatoire}
                          onChange={(event) => setFormData((current) => ({ ...current, obligatoire: event.target.checked }))}
                        />
                        <label htmlFor="obligatoire-individuelle" className="form-check-label">Matière obligatoire</label>
                      </div>
                      <div className="mb-3">
                        <label htmlFor="commentaire-individuel" className="form-label">Commentaire</label>
                        <textarea
                          id="commentaire-individuel"
                          className="form-control"
                          rows="2"
                          value={formData.commentaire}
                          onChange={(event) => setFormData((current) => ({ ...current, commentaire: event.target.value }))}
                        />
                      </div>
                      <button type="submit" className="btn btn-primary" disabled={ajouterMatiere.isPending || !formData.matiere}>
                        {ajouterMatiere.isPending ? 'Ajout...' : 'Ajouter la matière'}
                      </button>
                    </form>

                    <SISDataTable
                      title=""
                      data={matieresIndividuelles}
                      columns={individualColumns}
                      searchable={false}
                      exportable
                    />
                    <div className="mt-3">
                      {matieresIndividuelles.map((affectation) => (
                        <div key={affectation.id} className="d-flex justify-content-between align-items-center border rounded p-2 mb-2">
                          <div>
                            <strong>{affectation.matiere_nom}</strong>
                            <div className="text-muted small">{affectation.commentaire || 'Aucun commentaire'}</div>
                          </div>
                          <button
                            type="button"
                            className="btn btn-outline-danger btn-sm"
                            onClick={() => handleRemove(affectation.id)}
                            disabled={retirerMatiere.isPending}
                          >
                            Retirer
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </Tab>
              </Tabs>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default EleveDetailPage;
