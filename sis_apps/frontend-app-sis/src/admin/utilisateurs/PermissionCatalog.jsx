import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box, Button, Checkbox, FormControlLabel, MenuItem, Paper, Stack,
  Table, TableBody, TableCell, TableHead, TablePagination, TableRow, TextField, Typography,
} from '@mui/material';

export const permissionCode = permission => `${permission.app_label}.${permission.codename}`;
const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('fr');
const actions = {
  view: 'Consulter', add: 'Ajouter', change: 'Modifier', delete: 'Supprimer', other: 'Autres actions',
};
const actionOf = permission => {
  const prefix = permission.codename.split('_')[0];
  return Object.hasOwn(actions, prefix) ? prefix : 'other';
};

const PermissionCatalog = ({
  label, permissions, value, onChange, disabled = false, readOnly = false, details = {},
}) => {
  const [query, setQuery] = useState('');
  const [app, setApp] = useState('');
  const [action, setAction] = useState('');
  const [selectedOnly, setSelectedOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(25);
  const selected = new Set(value.map(String));
  const matches = permissions.filter(permission => (
    (!app || permission.app_label === app)
    && (!action || actionOf(permission) === action)
    && (!selectedOnly || selected.has(String(permission.id)))
    && normalize(`${permission.name} ${permissionCode(permission)}`).includes(normalize(query.trim()))
  ));
  const currentPage = Math.min(page, Math.max(0, Math.ceil(matches.length / size) - 1));
  const visible = matches.slice(currentPage * size, (currentPage + 1) * size);
  const apps = [...new Set(permissions.map(permission => permission.app_label))].sort();
  const changeFilter = setter => event => { setter(event.target.value); setPage(0); };
  const update = (items, checked) => {
    const ids = new Set(items.map(item => String(item.id)));
    onChange(checked
      ? [...value, ...items.filter(item => !selected.has(String(item.id))).map(item => item.id)]
      : value.filter(id => !ids.has(String(id))));
  };
  return (
    <Paper component="section" aria-label={label} variant="outlined" sx={{ p: 2 }}>
      <Typography component="h3" variant="subtitle1">{label}</Typography>
      <Typography role="status" variant="body2" sx={{ mb: 2 }}>
        {value.length} sélectionnée(s) · {matches.length} résultat(s) sur {permissions.length}
      </Typography>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 1 }}>
        <TextField label="Rechercher une permission" value={query} onChange={changeFilter(setQuery)} fullWidth />
        <TextField select label="Module" value={app} onChange={changeFilter(setApp)} sx={{ minWidth: 160 }}>
          <MenuItem value="">Tous les modules</MenuItem>
          {apps.map(name => <MenuItem key={name} value={name}>{name}</MenuItem>)}
        </TextField>
        <TextField select label="Action" value={action} onChange={changeFilter(setAction)} sx={{ minWidth: 160 }}>
          <MenuItem value="">Toutes les actions</MenuItem>
          {Object.entries(actions).map(([code, name]) => <MenuItem key={code} value={code}>{name}</MenuItem>)}
        </TextField>
      </Stack>
      <FormControlLabel
        label={readOnly ? 'Uniquement les permissions accordées' : 'Uniquement la sélection'}
        control={(
          <Checkbox checked={selectedOnly} onChange={event => { setSelectedOnly(event.target.checked); setPage(0); }} />
        )}
      />
      {!readOnly && (
        <Stack direction="row" useFlexGap sx={{ gap: 1, flexWrap: 'wrap', mb: 1 }}>
          <Button type="button" disabled={disabled || !matches.length} onClick={() => update(matches, true)}>
            Sélectionner les résultats ({matches.length})
          </Button>
          <Button type="button" disabled={disabled || !matches.some(item => selected.has(String(item.id)))} onClick={() => update(matches, false)}>
            Retirer les résultats de la sélection
          </Button>
        </Stack>
      )}
      {!readOnly && <Typography variant="caption">Les actions en lot concernent tous les résultats filtrés, y compris les autres pages. Les autres sélections sont conservées. Enregistrez le formulaire pour appliquer.</Typography>}
      <Box sx={{ overflowX: 'auto', maxHeight: 480 }}>
        <Table size="small" aria-label={label}>
          <TableHead>
            <TableRow><TableCell>{readOnly ? 'Accordée' : 'Sélection'}</TableCell><TableCell>Permission</TableCell><TableCell>Code</TableCell>{readOnly && <TableCell>Origine et limites</TableCell>}</TableRow>
          </TableHead>
          <TableBody>
            {visible.map((permission, index) => {
              const items = matches.filter(item => item.app_label === permission.app_label);
              const count = items.filter(item => selected.has(String(item.id))).length;
              return (
                <React.Fragment key={permission.id}>
                  {(index === 0 || visible[index - 1].app_label !== permission.app_label) && (
                    <TableRow>
                      <TableCell colSpan={readOnly ? 4 : 3}>
                        {readOnly ? <strong>{permission.app_label}</strong> : (
                          <FormControlLabel
                            label={`Module ${permission.app_label} (${count}/${items.length})`}
                            control={(
                              <Checkbox
                                checked={count === items.length}
                                indeterminate={count > 0 && count < items.length}
                                disabled={disabled}
                                onChange={event => update(items, event.target.checked)}
                              />
                            )}
                          />
                        )}
                      </TableCell>
                    </TableRow>
                  )}
                  <TableRow>
                    <TableCell>
                      <Checkbox
                        checked={selected.has(String(permission.id))}
                        disabled={disabled || readOnly}
                        inputProps={{ 'aria-label': `${permission.name} (${permissionCode(permission)})` }}
                        onChange={event => update([permission], event.target.checked)}
                      />
                    </TableCell>
                    <TableCell>{permission.name}</TableCell>
                    <TableCell>{permissionCode(permission)}</TableCell>
                    {readOnly && <TableCell>{details[permission.id]}</TableCell>}
                  </TableRow>
                </React.Fragment>
              );
            })}
          </TableBody>
        </Table>
        {!matches.length && <Typography sx={{ p: 2 }}>Aucune permission ne correspond aux filtres.</Typography>}
      </Box>
      <TablePagination
        component="div"
        count={matches.length}
        page={currentPage}
        rowsPerPage={size}
        rowsPerPageOptions={[25, 50, 100]}
        onPageChange={(_event, next) => setPage(next)}
        onRowsPerPageChange={event => { setSize(Number(event.target.value)); setPage(0); }}
        labelRowsPerPage="Permissions par page"
        getItemAriaLabel={type => (type === 'next' ? 'Page suivante des permissions' : 'Page précédente des permissions')}
      />
    </Paper>
  );
};
PermissionCatalog.propTypes = {
  label: PropTypes.string.isRequired,
  permissions: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    name: PropTypes.string.isRequired,
    app_label: PropTypes.string.isRequired,
    codename: PropTypes.string.isRequired,
  })).isRequired,
  value: PropTypes.arrayOf(PropTypes.oneOfType([PropTypes.number, PropTypes.string])).isRequired,
  onChange: PropTypes.func,
  disabled: PropTypes.bool,
  readOnly: PropTypes.bool,
  details: PropTypes.objectOf(PropTypes.string),
};
export default PermissionCatalog;
