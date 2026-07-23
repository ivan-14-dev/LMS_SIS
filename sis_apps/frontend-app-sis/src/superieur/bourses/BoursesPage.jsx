import React, { useState } from 'react';
import { Row, Col, Card, Badge, Button, Modal, Form, ActionRow, Tabs, Tab } from '@openedx/paragon';
import { Add, Money, Check, Close } from '@openedx/paragon/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { 
  useTypesBourses, useDemandesBourses, useDemandeBourse,
  fetchApi, postApi, getSuperieurApiUrl 
} from '../../services/api';

const BoursesPage = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('demandes');
  const [showNewDemande, setShowNewDemande] = useState(false);
  const [selectedDemande, setSelectedDemande] = useState(null);

  const { data: types = [] } = useTypesBourses();
  const { data: demandes = [], isLoading: loadingDemandes } = useDemandesBourses();
  
  const { data: stats } = useQuery({
    queryKey: ['bourses-stats'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/demandes-bourses/statistiques/`),
  });

  const decisionMutation = useMutation({
    mutationFn: ({ id, data }) => postApi(`${getSuperieurApiUrl()}/demandes-bourses/${id}/decision/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['demandes-bourses'] });
      setSelectedDemande(null);
    },
  });

  const demandesColumns = [
    { Header: 'Étudiant', accessor: 'etudiant_nom' },
    { Header: 'Type de bourse', accessor: 'type_bourse_nom' },
    { Header: 'Année', accessor: 'annee_universitaire' },
    { Header: 'Date soumission', accessor: 'date_soumission' },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => {
        const variants = {
          brouillon: 'secondary',
          soumise: 'warning',
          en_instruction: 'info',
          acceptee: 'success',
          refusee: 'danger',
          liste_attente: 'warning',
        };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
  ];

  const typesColumns = [
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Catégorie', accessor: 'categorie' },
    { Header: 'Montant mensuel', accessor: 'montant_mensuel', Cell: ({ value }) => `${value} €` },
    { Header: 'Durée (mois)', accessor: 'duree_mois' },
    {
      Header: 'Actif',
      accessor: 'actif',
      Cell: ({ value }) => value ? <Badge variant="success">Oui</Badge> : <Badge variant="danger">Non</Badge>,
    },
  ];

  const handleDecision = (decision) => {
    if (!selectedDemande) return;
    decisionMutation.mutate({
      id: selectedDemande.id,
      data: { decision, motif: '' },
    });
  };

  return (
    <div>
      <PageHeader
        title="Gestion des bourses"
        subtitle="Demandes, attributions et versements"
        actions={
          <Button variant="primary" iconBefore={Add} onClick={() => setShowNewDemande(true)}>
            Nouvelle demande
          </Button>
        }
      />

      {/* Stats */}
      <Row className="mb-4">
        <Col md={3}>
          <StatCard
            title="Total demandes"
            value={stats?.total_demandes || 0}
            icon={<Money />}
            variant="primary"
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="En attente"
            value={stats?.demandes_en_attente || 0}
            icon={<Money />}
            variant="warning"
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="Acceptées"
            value={stats?.demandes_acceptees || 0}
            icon={<Money />}
            variant="success"
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="Montant attribué"
            value={`${stats?.montant_total_attribue || 0} €`}
            icon={<Money />}
            variant="primary"
          />
        </Col>
      </Row>

      <Card>
        <Card.Body>
          <Tabs activeKey={activeTab} onSelect={setActiveTab}>
            <Tab eventKey="demandes" title="Demandes de bourses">
              <div className="pt-3">
                <SISDataTable
                  title="Liste des demandes"
                  data={demandes}
                  columns={demandesColumns}
                  loading={loadingDemandes}
                  onRowClick={(row) => setSelectedDemande(row.original)}
                  searchable
                  exportable
                />
              </div>
            </Tab>
            <Tab eventKey="types" title="Types de bourses">
              <div className="pt-3">
                <SISDataTable
                  title="Types de bourses disponibles"
                  data={types}
                  columns={typesColumns}
                  searchable
                />
              </div>
            </Tab>
            <Tab eventKey="attributions" title="Attributions">
              <div className="pt-3">
                <p className="text-muted">Attributions de bourses en cours...</p>
              </div>
            </Tab>
          </Tabs>
        </Card.Body>
      </Card>

      {/* Modal détail demande */}
      <Modal
        title="Détail de la demande"
        isOpen={!!selectedDemande}
        onClose={() => setSelectedDemande(null)}
        size="lg"
      >
        {selectedDemande && (
          <div>
            <dl className="row">
              <dt className="col-sm-4">Étudiant</dt>
              <dd className="col-sm-8">{selectedDemande.etudiant_nom}</dd>
              
              <dt className="col-sm-4">Type de bourse</dt>
              <dd className="col-sm-8">{selectedDemande.type_bourse_nom}</dd>
              
              <dt className="col-sm-4">Année</dt>
              <dd className="col-sm-8">{selectedDemande.annee_universitaire}</dd>
              
              <dt className="col-sm-4">Statut</dt>
              <dd className="col-sm-8">
                <Badge>{selectedDemande.statut}</Badge>
              </dd>
              
              <dt className="col-sm-4">Date soumission</dt>
              <dd className="col-sm-8">{selectedDemande.date_soumission || 'Non soumise'}</dd>
            </dl>

            {selectedDemande.statut === 'soumise' && (
              <ActionRow>
                <Button 
                  variant="danger" 
                  iconBefore={Close}
                  onClick={() => handleDecision('refusee')}
                  disabled={decisionMutation.isPending}
                >
                  Refuser
                </Button>
                <Button 
                  variant="success" 
                  iconBefore={Check}
                  onClick={() => handleDecision('acceptee')}
                  disabled={decisionMutation.isPending}
                >
                  Accepter
                </Button>
              </ActionRow>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default BoursesPage;
