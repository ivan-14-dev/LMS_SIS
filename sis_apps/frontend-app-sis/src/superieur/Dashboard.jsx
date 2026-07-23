import React from 'react';
import { Row, Col, Card, Icon } from '@openedx/paragon';
import { People, School, Assignment, Grade, Money, CalendarMonth } from '@openedx/paragon/icons';
import { useQuery } from '@tanstack/react-query';
import { fetchApi, getSuperieurApiUrl } from '../services/api';
import { StatCard, PageHeader } from '../components/common';

const Dashboard = () => {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/dashboard/stats/`),
  });

  const { data: recentActivities } = useQuery({
    queryKey: ['recent-activities'],
    queryFn: () => fetchApi(`${getSuperieurApiUrl()}/dashboard/activites/`),
  });

  return (
    <div>
      <PageHeader
        title="Tableau de bord"
        subtitle="Vue d'ensemble du système d'information universitaire"
      />

      {/* Stats Cards */}
      <Row className="mb-4">
        <Col md={3}>
          <StatCard
            title="Étudiants inscrits"
            value={stats?.total_etudiants || '—'}
            icon={<Icon src={People} />}
            variant="primary"
            loading={isLoading}
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="Formations actives"
            value={stats?.total_formations || '—'}
            icon={<Icon src={School} />}
            variant="success"
            loading={isLoading}
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="Inscriptions en cours"
            value={stats?.inscriptions_en_cours || '—'}
            icon={<Icon src={Assignment} />}
            variant="warning"
            loading={isLoading}
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="Examens à venir"
            value={stats?.examens_a_venir || '—'}
            icon={<Icon src={CalendarMonth} />}
            variant="danger"
            loading={isLoading}
          />
        </Col>
      </Row>

      <Row className="mb-4">
        <Col md={3}>
          <StatCard
            title="Bourses actives"
            value={stats?.bourses_actives || '—'}
            icon={<Icon src={Money} />}
            variant="success"
            loading={isLoading}
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="Moyenne générale"
            value={stats?.moyenne_generale ? `${stats.moyenne_generale}/20` : '—'}
            icon={<Icon src={Grade} />}
            variant="primary"
            loading={isLoading}
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="Stages en cours"
            value={stats?.stages_en_cours || '—'}
            icon={<Icon src={Assignment} />}
            variant="warning"
            loading={isLoading}
          />
        </Col>
        <Col md={3}>
          <StatCard
            title="Mémoires soutenus"
            value={stats?.memoires_soutenus || '—'}
            icon={<Icon src={School} />}
            variant="success"
            loading={isLoading}
          />
        </Col>
      </Row>

      {/* Recent Activities & Quick Actions */}
      <Row>
        <Col md={8}>
          <Card className="mb-4">
            <Card.Header>
              <Card.Title>Activités récentes</Card.Title>
            </Card.Header>
            <Card.Body>
              {recentActivities?.length > 0 ? (
                <ul className="list-unstyled">
                  {recentActivities.map((activity, index) => (
                    <li key={index} className="py-2 border-bottom">
                      <div className="d-flex justify-content-between">
                        <div>
                          <strong>{activity.titre}</strong>
                          <p className="text-muted mb-0 small">{activity.description}</p>
                        </div>
                        <small className="text-muted">{activity.date}</small>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted text-center">Aucune activité récente</p>
              )}
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="mb-4">
            <Card.Header>
              <Card.Title>Actions rapides</Card.Title>
            </Card.Header>
            <Card.Body>
              <div className="d-grid gap-2">
                <a href="/superieur/etudiants" className="btn btn-outline-primary">
                  Nouvel étudiant
                </a>
                <a href="/superieur/inscriptions" className="btn btn-outline-primary">
                  Nouvelle inscription
                </a>
                <a href="/superieur/notes" className="btn btn-outline-primary">
                  Saisir des notes
                </a>
                <a href="/superieur/examens" className="btn btn-outline-primary">
                  Planifier un examen
                </a>
              </div>
            </Card.Body>
          </Card>

          <Card>
            <Card.Header>
              <Card.Title>Année universitaire</Card.Title>
            </Card.Header>
            <Card.Body>
              <h4 className="text-center">{stats?.annee_courante || '2025-2026'}</h4>
              <p className="text-center text-muted mb-0">
                Semestre {stats?.semestre_courant || '1'} en cours
              </p>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
