import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import CollectionPagination from './CollectionPagination';

it.each([undefined, { count: 0, next: null, previous: null }])('does not show pagination before results or for an empty first page: %j', data => {
  render(<CollectionPagination data={data} page={1} setPage={jest.fn()} />);
  expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
});

it('shows only the total when all results fit on one page', () => {
  render(<CollectionPagination data={{ count: 3 }} page={1} setPage={jest.fn()} label="Dossiers" />);
  expect(screen.getByRole('navigation', { name: 'Pagination — Dossiers' })).toHaveTextContent('3 résultat(s)');
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

it('preserves a way back from an emptied later page without submitting its surrounding form', () => {
  const change = jest.fn();
  const submit = jest.fn(event => event.preventDefault());
  render(
    <form onSubmit={submit}>
      <CollectionPagination data={{ count: 0 }} page={2} setPage={change} />
    </form>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Page précédente' }));
  expect(change).toHaveBeenCalledWith(1);
  expect(submit).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Page suivante' })).toBeDisabled();
});

it('preserves pagination callbacks and disables navigation during an operation', () => {
  const change = jest.fn();
  const props = { data: { count: 21, next: '?page=2' }, page: 1, setPage: change };
  const { rerender } = render(<CollectionPagination {...props} />);
  fireEvent.click(screen.getByRole('button', { name: 'Page suivante' }));
  expect(change).toHaveBeenCalledWith(2);
  rerender(<CollectionPagination {...props} disabled />);
  fireEvent.click(screen.getByRole('button', { name: 'Page suivante' }));
  expect(change).toHaveBeenCalledTimes(1);
});
