import React, { useEffect, useState } from 'react';
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
  <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
    {editable && (
      <Button onClick={(event) => { event.stopPropagation(); openForm(cell.row.original); }}>Modifier</Button>
    )}
    {actions.filter(action => !action.statuses || action.statuses.includes(cell.row.original[action.statusField || 'statut'])).map(action => (
      <Button
        key={`${action.endpoint}-${action.label}`}
        onClick={(event) => { event.stopPropagation(); runAction(action, cell.row.original); }}
      >
        {action.label}
      </Button>
    ))}
  </Stack>
);

const selectRecord = (onSelect, row) => onSelect(row.original);

const formValue = (field, detail) => {
  const emptyValue = field.type === 'checkbox' ? false : '';
  const value = detail[field.name] ?? field.defaultValue ?? (field.multiple ? [] : emptyValue);
  if (field.resource && value && typeof value === 'object') {
    return field.multiple ? value.map(item => item.id ?? item) : value.id;
  }
  if (field.type !== 'datetime-local' || !value) { return value; }
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, -1);
};

const ResourceManager = ({
  variant, resource, title, columns, fields, actions, onSelect, children, searchable,
  filters, fixedValues, allowCreate, allowEdit, onSaved, headingLevel, showHeading,
}) => {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState('');
  const [record, setRecord] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [values, setValues] = useState({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [exporting, setExporting] = useState(false);
  const client = useQueryClient();
  const url = resourceUrl(variant, resource);
  const handleSelect = onSelect ? row => selectRecord(onSelect, row) : undefined;
  const queryKey = ['resource', url];
  const filtersKey = JSON.stringify(filters);
  useEffect(() => { setPage(0); }, [filtersKey]);
  const activeFields = pendingAction?.fields || fields;
  const query = useQuery({
    queryKey: [...queryKey, filters, page, pageSize, search],
    queryFn: ({ signal }) => fetchResourcePage(url, {
      ...filters, page: page + 1, page_size: pageSize, search,
    }, { signal }),
  });
  const referenceFields = activeFields.filter(field => field.resource);
  const refUrl = referenceResource => resourceUrl(variant, referenceResource);
  const references = useQueries({
    queries: referenceFields.map(field => ({
      queryKey: ['reference', resourceUrl(variant, field.resource), field.filters || {}],
      queryFn: ({ signal }) => fetchAllResourcePages(refUrl(field.resource), field.filters || {}, { signal }),
      enabled: Boolean(record),
    })),
  });
  const referenceError = references.find(reference => reference.error)?.error;
  const saving = useMutation({
    mutationFn: async () => {
      const payload = pendingAction ? {} : { ...fixedValues };
      activeFields.filter(field => pendingAction || !record.id || !field.createOnly).forEach((field) => {
        const value = values[field.name];
        const numericReference = field.resource && field.valueType !== 'string' && (!field.valueField || field.valueField === 'id');
        if (value !== '' && value !== undefined) {
          if (field.multiple) {
            payload[field.name] = numericReference ? value.map(Number) : value;
          } else if (field.type === 'datetime-local') {
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
      if (pendingAction) { return postApi(`${url}${record.id}/${pendingAction.endpoint}/`, payload); }
      return record.id ? patchApi(`${url}${record.id}/`, payload) : postApi(url, payload);
    },
    onSuccess: (result) => {
      setRecord(null);
      setPendingAction(null);
      setNotice(pendingAction ? `${pendingAction.label} : opération effectuée.` : 'Enregistrement effectué.');
      client.invalidateQueries({ queryKey: ['resource'] });
      client.invalidateQueries({ queryKey: ['reference'] });
      client.invalidateQueries({ queryKey: ['workflow-history', variant] });
      onSaved?.(result);
    },
    onError: failure => setError(apiErrorMessage(failure)),
  });

  const openForm = async (selected = {}) => {
    setError('');
    setNotice('');
    setPendingAction(null);
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
    setNotice('');
    if (action.fields?.length) {
      setPendingAction(action);
      setValues(Object.fromEntries(action.fields.map(field => [field.name, formValue(field, row)])));
      setRecord(row);
      return;
    }
    try {
      await postApi(`${url}${row.id}/${action.endpoint}/`, {});
      setNotice(`${action.label} : opération effectuée.`);
      client.invalidateQueries({ queryKey: ['resource'] });
      client.invalidateQueries({ queryKey: ['workflow-history', variant] });
    } catch (failure) {
      setError(apiErrorMessage(failure));
    }
  };

  const exportAll = async () => {
    setExporting(true);
    setError('');
    try {
      exportRecords(title, columns, await fetchAllResourcePages(url, { ...filters, ...(search ? { search } : {}) }));
    } catch (failure) {
      setError(apiErrorMessage(failure));
    } finally {
      setExporting(false);
    }
  };

  const displayedColumns = [...columns];
  const editable = allowEdit && fields.some(field => !field.createOnly);
  if ((allowEdit && fields.length) || actions.length) {
    displayedColumns.push({
      Header: 'Actions',
      accessor: 'id',
      Cell: actionButtons.bind(null, editable, openForm, actions, runAction),
    });
  }
  return (
    <Box component="section" aria-label={title} sx={{ minWidth: 0 }}>
      {showHeading && <Typography variant={headingLevel === 1 ? 'h4' : 'h3'} component={`h${headingLevel}`} gutterBottom>{title}</Typography>}
      {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}
      {(error || query.error) && <Alert severity="error" sx={{ mb: 2 }}>{error || apiErrorMessage(query.error)}</Alert>}
      <SISDataTable
        title={title}
        showTitle={false}
        toolbarActions={(
          <>
            <Button onClick={exportAll} disabled={exporting || query.isLoading}>
              {exporting ? 'Export en cours…' : 'Exporter tous les résultats'}
            </Button>
            {allowCreate && fields.length > 0 && <Button variant="contained" onClick={() => openForm()}>Ajouter</Button>}
          </>
        )}
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
        <Box component="form" onSubmit={(event) => { event.preventDefault(); event.stopPropagation(); saving.mutate(); }}>
          <DialogTitle>{pendingAction?.label || (record?.id ? 'Modifier' : 'Ajouter')} — {title}</DialogTitle>
          <DialogContent>
            {error && <Alert severity="error">{error}</Alert>}
            {referenceError && <Alert severity="error">{apiErrorMessage(referenceError)}</Alert>}
            {activeFields.filter(field => pendingAction || !record?.id || !field.createOnly).map((field) => {
              if (field.type === 'checkbox') {
                return (
                  <FormControlLabel
                    key={field.name}
                    label={field.label}
                    helperText={field.helpText}
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
                  value={values[field.name] ?? (field.multiple ? [] : '')}
                  onChange={event => setValues({ ...values, [field.name]: event.target.value })}
                  fullWidth
                  margin="normal"
                  disabled={reference?.isLoading}
                  slotProps={{
                    inputLabel: { shrink: true },
                    select: { multiple: Boolean(field.multiple) },
                    htmlInput: { step: ['number', 'time', 'datetime-local'].includes(field.type) ? 'any' : undefined },
                  }}
                >
                  {!field.required && !field.multiple && <MenuItem value="">—</MenuItem>}
                  {choices.map(choice => <MenuItem key={choice.value} value={choice.value}>{choice.label}</MenuItem>)}
                </TextField>
              );
            })}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setRecord(null)} disabled={saving.isPending}>Annuler</Button>
            <Button type="submit" variant="contained" disabled={saving.isPending || Boolean(referenceError)}>
              {saving.isPending ? 'Enregistrement…' : pendingAction?.label || 'Enregistrer'}
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
  headingLevel: PropTypes.oneOf([1, 2, 3]),
  showHeading: PropTypes.bool,
  columns: PropTypes.arrayOf(PropTypes.shape({
    Header: PropTypes.string.isRequired,
    accessor: PropTypes.string.isRequired,
    Cell: PropTypes.func,
  })).isRequired,
  fields: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    helpText: PropTypes.string,
    type: PropTypes.string,
    resource: PropTypes.string,
    required: PropTypes.bool,
    createOnly: PropTypes.bool,
    multiline: PropTypes.bool,
    multiple: PropTypes.bool,
    filters: PropTypes.objectOf(PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool])),
    labelField: PropTypes.string,
    valueField: PropTypes.string,
    valueType: PropTypes.oneOf(['string', 'number']),
    defaultValue: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool]),
    choices: PropTypes.arrayOf(PropTypes.shape({
      value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      label: PropTypes.string.isRequired,
    })),
  })),
  actions: PropTypes.arrayOf(PropTypes.shape({
    label: PropTypes.string.isRequired,
    endpoint: PropTypes.string.isRequired,
    statusField: PropTypes.string,
    statuses: PropTypes.arrayOf(PropTypes.oneOfType([PropTypes.string, PropTypes.bool])),
    fields: PropTypes.arrayOf(PropTypes.shape({
      name: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
    })),
  })),
  onSelect: PropTypes.func,
  onSaved: PropTypes.func,
  children: PropTypes.node,
  searchable: PropTypes.bool,
  filters: PropTypes.objectOf(PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool])),
  fixedValues: PropTypes.objectOf(PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.bool])),
  allowCreate: PropTypes.bool,
  allowEdit: PropTypes.bool,
};

ResourceManager.defaultProps = {
  headingLevel: 1,
  showHeading: true,
  fields: [],
  actions: [],
  onSelect: undefined,
  onSaved: undefined,
  children: null,
  searchable: true,
  filters: {},
  fixedValues: {},
  allowCreate: true,
  allowEdit: true,
};

export default ResourceManager;
