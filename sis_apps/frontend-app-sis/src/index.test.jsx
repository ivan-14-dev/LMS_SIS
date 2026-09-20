import ReactDOM from 'react-dom';
import { render, screen } from '@testing-library/react';
import {
  APP_INIT_ERROR, APP_READY, auth, getConfig, initialize, subscribe,
} from '@edx/frontend-platform';
import './index';

jest.mock('react-dom', () => ({
  ...jest.requireActual('react-dom'),
  render: jest.fn(),
}));
jest.mock('@edx/frontend-platform', () => ({
  APP_INIT_ERROR: 'app.init.error',
  APP_READY: 'app.ready',
  auth: jest.fn(),
  getConfig: jest.fn(() => ({})),
  initialize: jest.fn(),
  subscribe: jest.fn(),
}));
jest.mock('@edx/frontend-platform/react', () => ({
  AppProvider: jest.fn(({ children }) => children),
}));
jest.mock('./App', () => function MockApp() {
  return <p>SIS application</p>;
});

const ready = subscribe.mock.calls.find(([event]) => event === APP_READY)[1];
const failed = subscribe.mock.calls.find(([event]) => event === APP_INIT_ERROR)[1];
const initializationOptions = initialize.mock.calls[0][0];

beforeEach(() => {
  ReactDOM.render.mockClear();
  auth.mockReset();
  getConfig.mockReturnValue({});
});

it('registers lifecycle handlers before initializing authentication', () => {
  expect(subscribe.mock.invocationCallOrder[0]).toBeLessThan(initialize.mock.invocationCallOrder[0]);
  expect(subscribe.mock.invocationCallOrder[1]).toBeLessThan(initialize.mock.invocationCallOrder[0]);
  expect(initializationOptions.requireAuthenticatedUser).toBe(true);
  expect(initializationOptions.hydrateAuthenticatedUser).toBe(true);
});

it('waits for LMS authentication in live mode', async () => {
  const authentication = Promise.resolve('authenticated');
  auth.mockReturnValue(authentication);
  getConfig.mockReturnValue({ USE_MOCK_API: 'false' });

  expect(initializationOptions.handlers.auth(true, true)).toBe(authentication);
  expect(auth).toHaveBeenCalledWith(true, true);
  expect(ReactDOM.render).not.toHaveBeenCalled();
  await authentication;
});

it('does not hide an authentication failure by switching to demo mode', async () => {
  const error = new Error('Authentication unavailable');
  auth.mockRejectedValue(error);

  await expect(initializationOptions.handlers.auth(true, true)).rejects.toBe(error);
  expect(ReactDOM.render).not.toHaveBeenCalled();
});

it.each([true, 'true'])('permits an explicit demonstration without LMS login (%p)', (flag) => {
  getConfig.mockReturnValue({ USE_MOCK_API: flag });

  initializationOptions.handlers.auth(true, true);

  expect(auth).not.toHaveBeenCalled();
  ready();
  render(ReactDOM.render.mock.calls[0][0]);
  expect(screen.getByRole('status')).toHaveTextContent('Mode démonstration');
  expect(screen.getByRole('status')).toHaveTextContent('ne sont pas enregistrées');
});

it('renders the application after initialization without a demo banner in live mode', () => {
  ready();
  render(ReactDOM.render.mock.calls[0][0]);

  expect(screen.getByText('SIS application')).toBeInTheDocument();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

it('shows a safe startup error rather than application or simulated data', () => {
  failed(new Error('Private server details'));
  render(ReactDOM.render.mock.calls[0][0]);

  expect(screen.getByRole('alert')).toHaveTextContent('Impossible de démarrer le SIS');
  expect(screen.queryByText('SIS application')).not.toBeInTheDocument();
  expect(screen.queryByText('Private server details')).not.toBeInTheDocument();
});
