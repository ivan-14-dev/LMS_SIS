/* eslint import/no-extraneous-dependencies: ["error", { "devDependencies": true }] */
import React from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { IntlProvider } from '@edx/frontend-platform/i18n';

/**
 * Create a fresh QueryClient for each test
 */
export const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      cacheTime: 0,
    },
    mutations: {
      retry: false,
    },
  },
});

/**
 * Wrapper component with all providers needed for testing
 */
// eslint-disable-next-line react/prop-types
export const AllTheProviders = ({ children }) => {
  const queryClient = createTestQueryClient();

  return (
    // eslint-disable-next-line react/jsx-filename-extension
    <QueryClientProvider client={queryClient}>
      <IntlProvider locale="fr">
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </IntlProvider>
    </QueryClientProvider>
  );
};

/**
 * Custom render function that wraps component with all providers
 */
export const renderWithProviders = (ui, options) => render(ui, { wrapper: AllTheProviders, ...options });

/**
 * Mock API response helper
 */
export const mockApiResponse = (data, delay = 0) => new Promise((resolve) => {
  setTimeout(() => resolve({ data }), delay);
});

/**
 * Mock API error helper
 */
// Preserve the plain-object rejection shape used by the mock API.
// eslint-disable-next-line prefer-promise-reject-errors
export const mockApiError = (message = 'API Error', status = 500) => Promise.reject({
  response: {
    status,
    data: { message },
  },
});

// Re-export everything from testing-library
export * from '@testing-library/react';
export { renderWithProviders as render };
