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
export const AllTheProviders = ({ children }) => {
  const queryClient = createTestQueryClient();

  return (
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
export const renderWithProviders = (ui, options) => {
  return render(ui, { wrapper: AllTheProviders, ...options });
};

/**
 * Mock API response helper
 */
export const mockApiResponse = (data, delay = 0) => {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ data }), delay);
  });
};

/**
 * Mock API error helper
 */
export const mockApiError = (message = 'API Error', status = 500) => {
  return Promise.reject({
    response: {
      status,
      data: { message },
    },
  });
};

// Re-export everything from testing-library
export * from '@testing-library/react';
export { renderWithProviders as render };
