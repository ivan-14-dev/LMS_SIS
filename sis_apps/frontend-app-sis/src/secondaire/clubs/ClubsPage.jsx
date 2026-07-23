import React from 'react';
import { Badge, Button, Row, Col, Tabs, Tab, Card } from '@openedx/paragon';
import { Add, Group } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useClubs, useMembresClub, useActivitesClub } from '../../services/api';

const ClubsPage = () => {
  const { data: clubs = [], isLoading: loadingClubs } = useClubs();
  const { data: activites = [], isLoading: loadingActivites } = useActivitesClub();

  const clubsColumns = [
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Catégorie', accessor: 'categorie' },
    { Header: 'Responsable', accessor: 'responsable_nom' },
    { Header: 'Membres', accessor: 'nb_membres' },
    { Header: 'Jour activité', accessor: 'jour_activite' },
    { Header: 'Horaire', accessor: 'horaire' },
    {
      Header: 'Statut',
      accessor: 'actif',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'secondary'}>{value ? 'Actif' : 'Inactif'}</Badge>
      ),
    },
  ];

  const activitesColumns = [
    { Header: 'Date', accessor: 'date' },
    { Header: 'Club', accessor: 'club_nom' },
    { Header: 'Titre', accessor: 'titre' },
    { Header: 'Participants', accessor: 'nb_participants' },
    {
      Header: 'Type',
      accessor: 'type',
      Cell: ({ value }) => {
        const variants = {
          reunion: 'primary',
          sortie: 'success',
          competition: 'warning',
          formation: 'info',
        };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
    {
      Header: 'Statut',
      accessor: 'statut',
      Cell: ({ value }) => (
        <Badge variant={value === 'termine' ? 'success' : value === 'planifie' ? 'info' : 'secondary'}>
          {value}
        </Badge>
      ),
    },
  ];

  const totalMembres = clubs.reduce((sum, c) => sum + (c.nb_membres || 0), 0);

  return (
    <div>
      <PageHeader
        title="Clubs & Activités"
        subtitle="Gestion des clubs et activités périscolaires"
        actions={[
          { label: 'Nouveau club', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />
      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Clubs actifs" value={clubs.filter(c => c.actif).length} icon={<Group />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Total membres" value={totalMembres} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Activités (mois)" value={activites.length} variant="info" />
        </Col>
        <Col md={3}>
          <StatCard title="Moy. membres/club" value={clubs.length ? Math.round(totalMembres / clubs.length) : 0} variant="warning" />
        </Col>
      </Row>

      <Tabs defaultActiveKey="clubs">
        <Tab eventKey="clubs" title="Clubs">
          <div className="pt-3">
            <SISDataTable title="" data={clubs} columns={clubsColumns} loading={loadingClubs} searchable exportable />
          </div>
        </Tab>
        <Tab eventKey="activites" title="Activités">
          <div className="pt-3">
            <SISDataTable title="" data={activites} columns={activitesColumns} loading={loadingActivites} searchable exportable />
          </div>
        </Tab>
      </Tabs>
    </div>
  );
};

export default ClubsPage;
