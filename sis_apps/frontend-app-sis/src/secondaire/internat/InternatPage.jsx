import React from 'react';
import { Badge, Button, Row, Col, Tabs, Tab } from '@openedx/paragon';
import { Add, Hotel } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useInternes, useChambres } from '../../services/api';

const InternatPage = () => {
  const { data: internesData, isLoading: loadingInternes } = useInternes();
  const { data: chambresData, isLoading: loadingChambres } = useChambres();
  
  const internes = Array.isArray(internesData) ? internesData : [];
  const chambres = Array.isArray(chambresData) ? chambresData : [];

  const internesColumns = [
    { Header: 'Matricule', accessor: 'eleve_matricule' },
    { Header: 'Élève', accessor: 'eleve_nom' },
    { Header: 'Classe', accessor: 'classe_nom' },
    { Header: 'Chambre', accessor: 'chambre_numero' },
    { Header: 'Bâtiment', accessor: 'batiment' },
    {
      Header: 'Paiement',
      accessor: 'paiement_ok',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'danger'}>{value ? 'À jour' : 'Impayé'}</Badge>
      ),
    },
    {
      Header: 'Statut',
      accessor: 'actif',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'secondary'}>{value ? 'Actif' : 'Inactif'}</Badge>
      ),
    },
  ];

  const chambresColumns = [
    { Header: 'Numéro', accessor: 'numero' },
    { Header: 'Bâtiment', accessor: 'batiment' },
    { Header: 'Étage', accessor: 'etage' },
    { Header: 'Capacité', accessor: 'capacite' },
    { Header: 'Occupants', accessor: 'nb_occupants' },
    {
      Header: 'Occupation',
      accessor: 'taux_occupation',
      Cell: ({ row }) => {
        const taux = Math.round((row.original.nb_occupants / row.original.capacite) * 100);
        return (
          <Badge variant={taux >= 100 ? 'danger' : taux >= 75 ? 'warning' : 'success'}>
            {taux}%
          </Badge>
        );
      },
    },
    {
      Header: 'Statut',
      accessor: 'disponible',
      Cell: ({ row }) => (
        <Badge variant={row.original.nb_occupants < row.original.capacite ? 'success' : 'secondary'}>
          {row.original.nb_occupants < row.original.capacite ? 'Disponible' : 'Complet'}
        </Badge>
      ),
    },
  ];

  const totalCapacite = chambres.reduce((sum, c) => sum + (c.capacite || 0), 0);
  const totalOccupants = internes.filter(i => i.actif).length;

  return (
    <div>
      <PageHeader
        title="Internat"
        subtitle="Gestion de l'hébergement des élèves"
        actions={[
          { label: 'Nouvel interne', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Internes actifs" value={totalOccupants} icon={<Hotel />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Capacité totale" value={totalCapacite} variant="info" />
        </Col>
        <Col md={3}>
          <StatCard title="Taux occupation" value={`${totalCapacite ? Math.round((totalOccupants / totalCapacite) * 100) : 0}%`} variant="warning" />
        </Col>
        <Col md={3}>
          <StatCard title="Paiements en retard" value={internes.filter(i => !i.paiement_ok).length} variant="danger" />
        </Col>
      </Row>

      <Tabs defaultActiveKey="internes">
        <Tab eventKey="internes" title="Internes">
          <div className="pt-3">
            <SISDataTable title="" data={internes} columns={internesColumns} loading={loadingInternes} searchable exportable />
          </div>
        </Tab>
        <Tab eventKey="chambres" title="Chambres">
          <div className="pt-3">
            <SISDataTable title="" data={chambres} columns={chambresColumns} loading={loadingChambres} searchable exportable />
          </div>
        </Tab>
      </Tabs>
    </div>
  );
};

export default InternatPage;
