import React from 'react';
import { Tabs, Tab, Card } from '@openedx/paragon';
import { PageHeader, SISDataTable } from '../../components/common';
import { useEmprunts } from '../../services/api';

const BibliothequePage = () => {
  const { data: emprunts = [], isLoading } = useEmprunts();

  const empruntColumns = [
    { Header: 'Ouvrage', accessor: 'ouvrage_titre' },
    { Header: 'Emprunteur', accessor: 'emprunteur_nom' },
    { Header: 'Date emprunt', accessor: 'date_emprunt' },
    { Header: 'Date retour prévue', accessor: 'date_retour_prevue' },
    { Header: 'Statut', accessor: 'statut' },
  ];

  return (
    <div>
      <PageHeader title="Bibliothèque" subtitle="Gestion des ouvrages et emprunts" />
      <Card>
        <Card.Body>
          <Tabs defaultActiveKey="emprunts">
            <Tab eventKey="emprunts" title="Emprunts">
              <div className="pt-3">
                <SISDataTable title="Emprunts en cours" data={emprunts} columns={empruntColumns} loading={isLoading} searchable />
              </div>
            </Tab>
            <Tab eventKey="catalogue" title="Catalogue">
              <div className="pt-3"><p className="text-muted">Catalogue des ouvrages...</p></div>
            </Tab>
            <Tab eventKey="reservations" title="Réservations">
              <div className="pt-3"><p className="text-muted">Réservations d'ouvrages...</p></div>
            </Tab>
          </Tabs>
        </Card.Body>
      </Card>
    </div>
  );
};

export default BibliothequePage;
