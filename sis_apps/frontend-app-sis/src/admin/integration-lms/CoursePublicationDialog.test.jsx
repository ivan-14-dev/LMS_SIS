import React from 'react';
import {
  act, fireEvent, render, screen, waitFor,
} from '@testing-library/react';
import {
  MemoryRouter, Outlet, Route, Routes,
} from 'react-router-dom';
import { getConfig } from '@edx/frontend-platform';
import {
  fetchApi, postApi, useIntegrationCourseMappings, useIntegrationHealth, useIntegrationOutboxEvents,
  useIntegrationStats, useIntegrationUserCandidates, useIntegrationUserMappings,
} from '../../services/api';
import CoursePublicationDialog from './CoursePublicationDialog';
import IntegrationLMSPage from './IntegrationLMSPage';

jest.mock('@edx/frontend-platform', () => ({ getConfig: jest.fn() }));
jest.mock('@edx/frontend-platform/auth', () => ({ getAuthenticatedHttpClient: jest.fn() }));
jest.mock('../../services/api', () => ({
  ...jest.requireActual('../../services/api'),
  fetchApi: jest.fn(),
  postApi: jest.fn(),
  useIntegrationCourseMappings: jest.fn(),
  useIntegrationHealth: jest.fn(),
  useIntegrationOutboxEvents: jest.fn(),
  useIntegrationStats: jest.fn(),
  useIntegrationUserCandidates: jest.fn(),
  useIntegrationUserMappings: jest.fn(),
}));

const course = {
  id: 7, course_id: 'course-v1:School+Math+2026', course_name: 'Mathématiques', actif: true,
};
const otherCourse = {
  ...course, id: 8, course_id: 'course-v1:School+History+2026', course_name: 'Histoire',
};
const revision = '0123456789abcdef01234567';
const newerRevision = 'abcdef0123456789abcdef01';
const operationId = 'c662e9bf-4a2d-4632-96a1-8cd285bacd75';
const review = { id: course.course_id, revision };
const success = {
  ...review, operation_id: operationId, published_version: '111111111111111111111111',
};
const deferred = () => {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
};
const dialog = (mapping = course, onClose = jest.fn(), canPublish = true) => (
  <CoursePublicationDialog mapping={mapping} onClose={onClose} canPublish={canPublish} />
);
const confirm = () => fireEvent.click(screen.getByRole('checkbox', { name: /J’ai examiné ce cours/ }));
const publish = () => fireEvent.click(screen.getByRole('button', { name: 'Publier cette révision' }));
const endpoint = variant => `https://${variant}.example/api/v1/integration/sync/course/7/publication/`;

beforeEach(() => {
  jest.clearAllMocks();
  getConfig.mockReturnValue({
    SIS_MODE: 'dual',
    SIS_SECONDAIRE_API_URL: 'https://secondaire.example/api/v1',
    SIS_SUPERIEUR_API_URL: 'https://superieur.example/api/v1',
  });
  window.history.replaceState({}, '', '/admin/integration-lms?sis=secondaire');
  crypto.randomUUID = jest.fn(() => operationId);
  fetchApi.mockResolvedValue(review);
  postApi.mockResolvedValue(success);
  [
    useIntegrationHealth, useIntegrationStats, useIntegrationUserMappings, useIntegrationOutboxEvents,
    useIntegrationUserCandidates,
  ].forEach(hook => hook.mockReturnValue({ data: {}, refetch: jest.fn() }));
  useIntegrationCourseMappings.mockReturnValue({
    data: { results: [course, { ...otherCourse, actif: false }], count: 2 },
    refetch: jest.fn(),
  });
});

it.each(['secondaire', 'superieur'])('requires review and human confirmation, then submits once in %s scope', async (variant) => {
  window.history.replaceState({}, '', `/admin/integration-lms?sis=${variant}`);
  const pendingReview = deferred();
  const pendingPublication = deferred();
  fetchApi.mockReturnValue(pendingReview.promise);
  postApi.mockReturnValue(pendingPublication.promise);
  const close = jest.fn();
  render(dialog(course, close));

  expect(screen.getByRole('button', { name: 'Publier cette révision' })).toBeDisabled();
  expect(screen.getByRole('checkbox')).toBeDisabled();
  await act(async () => pendingReview.resolve(review));
  expect(fetchApi).toHaveBeenCalledWith(endpoint(variant), { signal: expect.any(AbortSignal) });
  expect(screen.getByText(`Cours LMS : ${course.course_id}`)).toBeInTheDocument();
  expect(screen.getByText(`Révision examinée : ${revision}`)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Publier cette révision' })).toBeDisabled();
  expect(postApi).not.toHaveBeenCalled();

  confirm();
  publish();
  publish();
  expect(postApi).toHaveBeenCalledTimes(1);
  expect(postApi).toHaveBeenCalledWith(endpoint(variant), {
    operation_id: operationId, expected_revision: revision, confirm: true,
  });
  expect(screen.getByRole('button', { name: 'Fermer' })).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  expect(close).not.toHaveBeenCalled();
  expect(screen.queryByText(/Publication confirmée par Studio/)).not.toBeInTheDocument();

  await act(async () => pendingPublication.resolve(success));
  expect(screen.getByRole('alert')).toHaveTextContent(`Publication confirmée par Studio. Version publiée : ${success.published_version}`);
  expect(close).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Fermer' }));
  expect(close).toHaveBeenCalledTimes(1);
  expect(fetchApi).toHaveBeenCalledTimes(1);
});

it.each(['network', '502', 'invalid-confirmation'])('retains the exact operation after %s, including closing and reopening', async (failure) => {
  if (failure === 'network') {
    postApi.mockRejectedValueOnce(new Error('Connexion interrompue'));
  } else if (failure === '502') {
    postApi.mockRejectedValueOnce({ response: { status: 502, data: { error: 'Studio indisponible' } } });
  } else {
    postApi.mockResolvedValueOnce({ ...success, revision: newerRevision });
  }
  const close = jest.fn();
  const view = render(dialog(course, close));
  await screen.findByText(`Révision examinée : ${revision}`);
  confirm();
  publish();
  expect(await screen.findByText(/Publication non confirmée/)).toBeInTheDocument();
  expect(screen.queryByText(/Publication confirmée par Studio/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Examiner à nouveau' })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Fermer' }));
  expect(close).toHaveBeenCalledTimes(1);
  view.rerender(dialog(null, close));
  fetchApi.mockResolvedValue({ ...review, revision: newerRevision });
  view.rerender(dialog(course, close));
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  expect(screen.getByRole('button', { name: 'Réessayer la même publication' })).toBeDisabled();
  confirm();
  fireEvent.click(screen.getByRole('button', { name: 'Réessayer la même publication' }));
  await screen.findByText(/Publication confirmée par Studio/);
  expect(postApi.mock.calls).toEqual([
    [endpoint('secondaire'), { operation_id: operationId, expected_revision: revision, confirm: true }],
    [endpoint('secondaire'), { operation_id: operationId, expected_revision: revision, confirm: true }],
  ]);
  expect(crypto.randomUUID).toHaveBeenCalledTimes(1);
  expect(fetchApi).toHaveBeenCalledTimes(1);
});

it('requires an explicit new review and new confirmation after a revision conflict', async () => {
  postApi.mockRejectedValueOnce({ response: { status: 409, data: { error: 'La révision a changé.' } } });
  render(dialog());
  await screen.findByText(`Révision examinée : ${revision}`);
  confirm();
  publish();
  expect(await screen.findByText(/La révision a changé/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Publier cette révision' })).toBeDisabled();
  expect(fetchApi).toHaveBeenCalledTimes(1);
  expect(postApi).toHaveBeenCalledTimes(1);
  fetchApi.mockResolvedValue({ ...review, revision: newerRevision });
  fireEvent.click(screen.getByRole('button', { name: 'Examiner à nouveau' }));
  await screen.findByText(`Révision examinée : ${newerRevision}`);
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  expect(screen.getByRole('button', { name: 'Publier cette révision' })).toBeDisabled();
  expect(postApi).toHaveBeenCalledTimes(1);
});

it.each([
  ['inactive mapping', { ...course, actif: false }, true, false, /association de cours est désactivée/],
  ['non-admin', course, false, false, /réservée aux administrateurs/],
  ['demo mode', course, true, true, /mode démonstration/],
])('does not request or publish for %s', async (label, mapping, canPublish, mockMode, message) => {
  getConfig.mockReturnValue({ ...getConfig(), USE_MOCK_API: mockMode });
  render(dialog(mapping, jest.fn(), canPublish));
  expect(screen.getByRole('alert')).toHaveTextContent(message);
  expect(screen.getByRole('button', { name: 'Publier cette révision' })).toBeDisabled();
  expect(fetchApi).not.toHaveBeenCalled();
  expect(postApi).not.toHaveBeenCalled();
});

it.each([
  [{ ...review, id: otherCourse.course_id }, /n’a pas confirmé l’identité/],
  [{ ...review, revision: revision.toUpperCase() }, /n’a pas confirmé l’identité/],
  [null, /association désactivée/],
])('blocks publication when review is invalid or the server rejects an inactive mapping', async (response, message) => {
  if (response) {
    fetchApi.mockResolvedValue(response);
  } else {
    fetchApi.mockRejectedValue({ response: { status: 409, data: { error: 'association désactivée' } } });
  }
  render(dialog());
  expect(await screen.findByRole('alert')).toHaveTextContent(message);
  expect(screen.getByRole('checkbox')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Publier cette révision' })).toBeDisabled();
  expect(postApi).not.toHaveBeenCalled();
});

it('cancels review and ignores its late response after selecting another course', async () => {
  const pendingReview = deferred();
  fetchApi.mockReturnValueOnce(pendingReview.promise);
  const close = jest.fn();
  const view = render(dialog(course, close));
  const { signal } = fetchApi.mock.calls[0][1];
  fireEvent.click(screen.getByRole('button', { name: 'Annuler' }));
  expect(close).toHaveBeenCalledTimes(1);
  view.rerender(dialog(null, close));
  expect(signal.aborted).toBe(true);
  fetchApi.mockResolvedValue({ id: otherCourse.course_id, revision: newerRevision });
  view.rerender(dialog(otherCourse, close));
  await screen.findByText(`Révision examinée : ${newerRevision}`);
  await act(async () => pendingReview.resolve(review));
  expect(screen.getByText(`Cours LMS : ${otherCourse.course_id}`)).toBeInTheDocument();
  expect(screen.queryByText(`Révision examinée : ${revision}`)).not.toBeInTheDocument();
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  expect(postApi).not.toHaveBeenCalled();
});

it('isolates a late publication response from a different SIS scope and restores its own result', async () => {
  const pendingPublication = deferred();
  postApi.mockReturnValueOnce(pendingPublication.promise);
  const view = render(dialog());
  await screen.findByText(`Révision examinée : ${revision}`);
  confirm();
  publish();
  window.history.replaceState({}, '', '/admin/integration-lms?sis=superieur');
  fetchApi.mockResolvedValue({ ...review, revision: newerRevision });
  view.rerender(dialog());
  await screen.findByText(`Révision examinée : ${newerRevision}`);
  await act(async () => pendingPublication.resolve(success));
  expect(screen.queryByText(/Publication confirmée par Studio/)).not.toBeInTheDocument();
  expect(screen.queryByText(`Opération : ${operationId}`)).not.toBeInTheDocument();
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  expect(fetchApi.mock.calls.map(([url]) => url)).toEqual([endpoint('secondaire'), endpoint('superieur')]);
  window.history.replaceState({}, '', '/admin/integration-lms?sis=secondaire');
  view.rerender(dialog());
  expect(screen.getByText(/Publication confirmée par Studio/)).toBeInTheDocument();
  expect(postApi).toHaveBeenCalledTimes(1);
});

it('exposes only the qualified admin course action and keeps inactive and unrelated actions disabled', async () => {
  const page = staff => (
    <MemoryRouter>
      <Routes>
        <Route element={<Outlet context={{ profile: { is_staff: staff } }} />}>
          <Route index element={<IntegrationLMSPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
  const view = render(page(true));
  fireEvent.click(screen.getByRole('tab', { name: 'Cours' }));
  expect(screen.getByRole('button', { name: 'Créer cours manquants' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Examiner et publier Histoire' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Examiner et publier Mathématiques' })).toBeEnabled();
  screen.getAllByTestId('SyncIcon').forEach(icon => expect(icon.closest('button')).toBeDisabled());
  fireEvent.click(screen.getByRole('button', { name: 'Examiner et publier Mathématiques' }));
  await screen.findByRole('dialog');
  await waitFor(() => expect(fetchApi).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Annuler' }));
  view.rerender(page(false));
  expect(screen.queryByRole('button', { name: /Examiner et publier/ })).not.toBeInTheDocument();
  expect(postApi).not.toHaveBeenCalled();
});
