import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import {
  useMutation, useQueries, useQuery, useQueryClient,
} from '@tanstack/react-query';
import { fetchApi, patchApi, postApi } from '../../services/api';
import {
  apiErrorMessage, exportRecords, fetchAllResourcePages, fetchResourcePage, resourceUrl,
} from '../../services/resources';
import SISDataTable from './SISDataTable';

const actionButtons = (editable, openForm, actions, runAction, cell) => (
  <Stack direction="row" spacing={1}>
    {editable && (
      <Button onClick={(event) => { event.stopPropagation(); openForm(cell.row.original); }}>Modifier</Button>
    )}
    {actions.map(action => (
      <Button
        key={action.endpoint}
        onClick={(event) => { event.stopPropagation(); runAction(action, cell.row.original); }}
      >
        {action.label}
      </Button>
    ))}
  </Stack>
);

const selectRecord = (onSelect, row) => onSelect(row.original);

const formValue = (field, detail) => {
  const value = detail[field.name] ?? field.defaultValue ?? (field.type === 'checkbox' ? false : '');
  if (field.type !== 'datetime-local' || !value) { return value; }
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, -1);
};

const ResourceManager = ({
  variant, resource, title, columns, fields, actions, onSelect, children, searchable,
}) => {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState('');
  const [record, setRecord] = useState(null);
  const [values, setValues] = useState({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [exporting, setExporting] = useState(false);
  const client = useQueryClient();
  const url = resourceUrl(variant, resource);
  const handleSelect = onSelect ? row => selectRecord(onSelect, row) : undefined;
  const queryKey = ['resource', url];
  const query = useQuery({
    queryKey: [...queryKey, page, pageSize, search],
    queryFn: ({ signal }) => fetchResourcePage(url, { page: page + 1, page_size: pageSize, search }, { signal }),
  });
  const referenceFields = fields.filter(field => field.resource);
  const references = useQueries({
    queries: referenceFields.map(field => ({
      queryKey: ['reference', resourceUrl(variant, field.resource)],
      queryFn: ({ signal }) => fetchAllResourcePages(resourceUrl(variant, field.resource), {}, { signal }),
      enabled: Boolean(record),
    })),
  });
  const referenceError = references.find(reference => reference.error)?.error;
  const saving = useMutation({
    mutationFn: async () => {
      const payload = {};
      fields.filter(field => !record.id || !field.createOnly).forEach((field) => {
        const value = values[field.name];
        const numericReference = field.resource && (!field.valueField || field.valueField === 'id');
        if (value !== '' && value !== undefined) {
          if (field.type === 'datetime-local') {
            // Preserve the offset of an unchanged instant during a daylight-saving overlap.
            payload[field.name] = record[field.name] && value === formValue(field, record)
              ? record[field.name] : new Date(value).toISOString();
          } else {
            payload[field.name] = field.type === 'number' || numericReference ? Number(value) : value;
          }
        } else if (!field.required && record.id) {
          payload[field.name] = numericReference || ['number', 'date', 'time', 'datetime-local'].includes(field.type)
            ? null : '';
        }
      });
      return record.id ? patchApi(`${url}${record.id}/`, payload) : postApi(url, payload);
    },
    onSuccess: () => {
      setRecord(null);
      setNotice('Enregistrement effectué.');
      client.invalidateQueries({ queryKey });
      client.invalidateQueries({ queryKey: ['reference'] });
    },
    onError: failure => setError(apiErrorMessage(failure)),
  });

  const openForm = async (selected = {}) => {
    setError('');
    setNotice('');
    try {
      const detail = selected.id ? await fetchApi(`${url}${selected.id}/`) : selected;
      setValues(Object.fromEntries(fields.map(field => [
        field.name, formValue(field, detail),
      ])));
      setRecord(detail);
    } catch (failure) {
      setError(apiErrorMessage(failure));
    }
  };

  const runAction = async (action, row) => {
    setError('');
    try {
      await postApi(`${url}${row.id}/${action.endpoint}/`, {});
      setNotice(`${action.label} : opération effectuée.`);
      client.invalidateQueries({ queryKey });
    } catch (failure) {
      setError(apiErrorMessage(failure));
    }
  };

  const exportAll = async () => {
    setExporting(true);
    setError('');
    try {
      exportRecords(title, columns, await fetchAllResourcePages(url, search ? { search } : {}));
    } catch (failure) {
      setError(apiErrorMessage(failure));
    } finally {
      setExporting(false);
    }
  };

  const displayedColumns = [...columns];
  if (fields.length || actions.length) {
    displayedColumns.push({
      Header: 'Actions',
      accessor: 'id',
      Cell: actionButtons.bind(null, fields.some(field => !field.createOnly), openForm, actions, runAction),
    });
  }
  return (
    <Box component="section" aria-label={title}>
      <Typography variant="h4" component="h1" gutterBottom>{title}</Typography>
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        {fields.length > 0 && <Button variant="contained" onClick={() => openForm()}>Ajouter</Button>}
        <Button onClick={exportAll} disabled={exporting || query.isLoading}>
          {exporting ? 'Export en cours…' : 'Exporter tous les résultats'}
        </Button>
      </Stack>
      {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}
      {(error || query.error) && <Alert severity="error" sx={{ mb: 2 }}>{error || apiErrorMessage(query.error)}</Alert>}
      <SISDataTable
        title={title}
        columns={displayedColumns}
        data={query.data?.results || []}
        loading={query.isLoading}
        searchable={searchable}
        exportable={false}
        onRefresh={() => query.refetch()}
        onRowClick={handleSelect}
        serverPagination={{
          page,
          pageSize,
          count: query.data?.count || 0,
          search,
          onPageChange: setPage,
          onPageSizeChange: size => { setPageSize(size); setPage(0); },
          onSearchChange: value => { setSearch(value); setPage(0); },
        }}
      />
      {children}
      <Dialog open={Boolean(record)} onClose={() => !saving.isPending && setRecord(null)} fullWidth>
        <Box component="form" onSubmit={(event) => { event.preventDefault(); saving.mutate(); }}>
          <DialogTitle>{record?.id ? 'Modifier' : 'Ajouter'} — {title}</DialogTitle>
          <DialogContent>
            {error && <Alert severity="error">{error}</Alert>}
            {referenceError && <Alert severity="error">{apiErrorMessage(referenceError)}</Alert>}
            {fields.filter(field => !record?.id || !field.createOnly).map((field) => {
              if (field.type === 'checkbox') {
                return (
                  <FormControlLabel
                    key={field.name}
                    label={field.label}
                    control={(
                      <Checkbox
                        checked={Boolean(values[field.name])}
                        onChange={event => setValues({ ...values, [field.name]: event.target.checked })}
                      />
                    )}
                  />
                );
              }
              const reference = references[referenceFields.indexOf(field)];
              const choices = [...(field.choices || reference?.data?.map(item => ({
                value: item[field.valueField || 'id'],
                label: item[field.labelField || 'nom'] || item.full_name || item.libelle || item.username || item.id,
              })) || [])];
              if (field.valueField && values[field.name]
                && !choices.some(choice => choice.value === values[field.name])) {
                choices.push({ value: values[field.name], label: `${values[field.name]} (configuration conservée)` });
              }
              return (
                <TextField
                  key={field.name}
                  label={field.label}
                  type={field.type || 'text'}
                  select={Boolean(field.choices || field.resource)}
                  required={field.required}
                  multiline={field.multiline}
                  value={values[field.name] ?? ''}
                  onChange={event => setValues({ ...values, [field.name]: event.target.value })}
                  fullWidth
                  margin="normal"
                  disabled={reference?.isLoading}
                  slotProps={{
                    inputLabel: { shrink: true },
                    htmlInput: { step: ['number', 'time', 'datetime-local'].includes(field.type) ? 'any' : undefined },
                  }}
                >
                  {!field.required && <MenuItem value="">—</MenuItem>}
                  {choices.map(choice => <MenuItem key={choice.value} value={choice.value}>{choice.label}</MenuItem>)}
                </TextField>
              );
            })}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setRecord(null)} disabled={saving.isPending}>Annuler</Button>
            <Button type="submit" variant="contained" disabled={saving.isPending || Boolean(referenceError)}>
              {saving.isPending ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Box>
  );
};

ResourceManager.propTypes = {
  variant: PropTypes.oneOf(['secondaire', 'superieur', 'admin']).isRequired,
  resource: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  columns: PropTypes.arrayOf(PropTypes.shape({
    Header: PropTypes.string.isRequired,
    accessor: PropTypes.string.isRequired,
    Cell: PropTypes.func,
  })).isRequired,
  fields: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    type: PropTypes.string,
    resource: PropTypes.string,
    required: PropTypes.bool,
    createOnly: PropTypes.bool,
    multiline: PropTypes.bool,
    labelField: PropTypes.string,
    valueField: PropTypes.string,
    defaultValue: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool]),
    choices: PropTypes.arrayOf(PropTypes.shape({
      value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      label: PropTypes.string.isRequired,
    })),
  })),
  actions: PropTypes.arrayOf(PropTypes.shape({
    label: PropTypes.string.isRequired,
    endpoint: PropTypes.string.isRequired,
  })),
  onSelect: PropTypes.func,
  children: PropTypes.node,
  searchable: PropTypes.bool,
};

ResourceManager.defaultProps = {
  fields: [], actions: [], onSelect: undefined, children: null, searchable: true,
};

export default ResourceManager;
