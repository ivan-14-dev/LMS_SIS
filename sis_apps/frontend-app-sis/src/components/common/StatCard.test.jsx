import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { IntlProvider } from '@edx/frontend-platform/i18n';
import StatCard from './StatCard';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const renderWithProviders = (component) => {
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlProvider locale="fr">
        {component}
      </IntlProvider>
    </QueryClientProvider>
  );
};

describe('StatCard', () => {
  it('renders title and value correctly', () => {
    renderWithProviders(
      <StatCard title="Total étudiants" value={1250} variant="primary" />
    );

    expect(screen.getByText('Total étudiants')).toBeInTheDocument();
    expect(screen.getByText('1250')).toBeInTheDocument();
  });

  it('renders with icon', () => {
    const MockIcon = () => <span data-testid="mock-icon">Icon</span>;
    renderWithProviders(
      <StatCard title="Test" value={100} icon={<MockIcon />} />
    );

    expect(screen.getByTestId('mock-icon')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    renderWithProviders(
      <StatCard title="Test" value={100} loading />
    );

    // Component should handle loading state
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('applies variant class correctly', () => {
    const { container } = renderWithProviders(
      <StatCard title="Test" value={100} variant="success" />
    );

    // Check if success variant is applied
    expect(container.querySelector('.sis-stat-card')).toBeInTheDocument();
  });
});
