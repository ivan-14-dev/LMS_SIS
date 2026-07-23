import React from 'react';
import { Badge, Button, Row, Col } from '@openedx/paragon';
import { Add, Edit, Delete, People } from '@openedx/paragon/icons';
import { PageHeader, SISDataTable, StatCard } from '../../components/common';
import { useUtilisateurs } from '../../services/api';

const UtilisateursPage = () => {
  const { data: utilisateurs = [], isLoading } = useUtilisateurs();

  const columns = [
    { Header: 'Nom d\'utilisateur', accessor: 'username' },
    { Header: 'Nom', accessor: 'nom' },
    { Header: 'Prénom', accessor: 'prenom' },
    { Header: 'Email', accessor: 'email' },
    {
      Header: 'Rôle',
      accessor: 'role',
      Cell: ({ value }) => {
        const variants = {
          admin: 'danger',
          scolarite: 'primary',
          enseignant: 'success',
          etudiant: 'info',
          parent: 'warning',
        };
        return <Badge variant={variants[value] || 'secondary'}>{value}</Badge>;
      },
    },
    {
      Header: 'Statut',
      accessor: 'is_active',
      Cell: ({ value }) => (
        <Badge variant={value ? 'success' : 'secondary'}>{value ? 'Actif' : 'Inactif'}</Badge>
      ),
    },
    { Header: 'Dernière connexion', accessor: 'last_login' },
    {
      Header: 'Actions',
      accessor: 'id',
      Cell: () => (
        <>
          <Button size="sm" variant="outline-primary" iconBefore={Edit} className="me-1">Éditer</Button>
          <Button size="sm" variant="outline-danger" iconBefore={Delete}>Supprimer</Button>
        </>
      ),
    },
  ];

  const admins = utilisateurs.filter(u => u.role === 'admin').length;
  const actifs = utilisateurs.filter(u => u.is_active).length;

  return (
    <div>
      <PageHeader
        title="Utilisateurs"
        subtitle="Gestion des comptes utilisateurs"
        actions={[
          { label: 'Nouvel utilisateur', icon: <Add />, variant: 'primary', onClick: () => {} },
        ]}
      />

      <Row className="mb-4">
        <Col md={3}>
          <StatCard title="Total utilisateurs" value={utilisateurs.length} icon={<People />} variant="primary" />
        </Col>
        <Col md={3}>
          <StatCard title="Actifs" value={actifs} variant="success" />
        </Col>
        <Col md={3}>
          <StatCard title="Administrateurs" value={admins} variant="danger" />
        </Col>
        <Col md={3}>
          <StatCard title="Inactifs" value={utilisateurs.length - actifs} variant="secondary" />
        </Col>
      </Row>

      <SISDataTable title="Liste des utilisateurs" data={utilisateurs} columns={columns} loading={isLoading} searchable exportable />
    </div>
  );
};

export default UtilisateursPage;
