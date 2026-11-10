import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  fireEvent, render, screen, within,
} from '@testing-library/react';
import PermissionCatalog from './PermissionCatalog';

const permissions = [
  ...Array.from({ length: 30 }, (_item, index) => ({
    id: index + 1, name: `Consulter note ${index + 1}`, app_label: 'notes', codename: `view_note${index + 1}`,
  })),
  {
    id: 40, name: 'Modifier facture', app_label: 'paiements', codename: 'change_facture',
  },
];
const Harness = ({ disabled = false, readOnly = false }) => {
  const [value, setValue] = useState([40, 999]);
  return (
    <>
      <PermissionCatalog label="Catalogue" permissions={permissions} value={value} onChange={setValue} disabled={disabled} readOnly={readOnly} />
      <output aria-label="Sélection enregistrée">{JSON.stringify(value)}</output>
    </>
  );
};
Harness.propTypes = { disabled: PropTypes.bool, readOnly: PropTypes.bool };

it('selects all filtered pages, preserves hidden selections and supports partial module selection', () => {
  render(<Harness />);
  const catalogue = within(screen.getByRole('region', { name: 'Catalogue' }));
  fireEvent.change(catalogue.getByLabelText('Rechercher une permission'), { target: { value: 'notes.view_' } });
  fireEvent.click(catalogue.getByRole('button', { name: 'Sélectionner les résultats (30)' }));
  let selected = JSON.parse(screen.getByLabelText('Sélection enregistrée').textContent);
  expect(selected).toHaveLength(32);
  expect(selected).toEqual(expect.arrayContaining([1, 25, 30, 40, 999]));
  fireEvent.click(catalogue.getByRole('button', { name: 'Page suivante des permissions' }));
  fireEvent.click(catalogue.getByRole('checkbox', { name: 'Consulter note 30 (notes.view_note30)' }));
  expect(catalogue.getByRole('checkbox', { name: 'Module notes (29/30)' })).toHaveAttribute('data-indeterminate', 'true');
  fireEvent.click(catalogue.getByRole('button', { name: 'Retirer les résultats de la sélection' }));
  selected = JSON.parse(screen.getByLabelText('Sélection enregistrée').textContent);
  expect(selected).toEqual([40, 999]);
});

it('filters by action and keeps selections when filters are cleared', () => {
  render(<Harness />);
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Action' }));
  fireEvent.click(screen.getByRole('option', { name: 'Modifier' }));
  expect(screen.getByRole('checkbox', { name: /Modifier facture/ })).toBeChecked();
  expect(screen.queryByRole('checkbox', { name: /Consulter note/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Module paiements (1/1)' }));
  expect(screen.getByLabelText('Sélection enregistrée')).toHaveTextContent('[999]');
});

it('prevents bulk and individual changes in protected and read-only views', () => {
  const { rerender } = render(<Harness disabled />);
  expect(screen.getByRole('button', { name: 'Sélectionner les résultats (31)' })).toBeDisabled();
  expect(screen.getByRole('checkbox', { name: 'Consulter note 1 (notes.view_note1)' })).toBeDisabled();
  rerender(<Harness readOnly />);
  expect(screen.queryByRole('button', { name: /Sélectionner les résultats/ })).not.toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: 'Consulter note 1 (notes.view_note1)' })).toBeDisabled();
});
