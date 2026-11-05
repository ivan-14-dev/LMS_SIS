import React, { useState, useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Card,
  CardContent,
  Box,
  Typography,
  TextField,
  InputAdornment,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Search as SearchIcon,
  Download as DownloadIcon,
  Add as AddIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { exportRecords } from '../../services/resources';
import StatusBadge from './StatusBadge';

const SISDataTable = ({
  title,
  data = [],
  columns,
  loading,
  onRowClick,
  onAdd,
  addButtonLabel,
  searchable,
  exportable,
  pageSize: initialPageSize,
  emptyMessage,
  onRefresh,
  serverPagination,
  showTitle,
  toolbarActions,
}) => {
  const [searchValue, setSearchValue] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(initialPageSize);

  // Ensure data is always an array
  const safeData = useMemo(() => {
    if (Array.isArray(data)) { return data; }
    if (data?.results && Array.isArray(data.results)) { return data.results; }
    return [];
  }, [data]);

  const filteredData = useMemo(() => {
    if (serverPagination || !searchable || !searchValue) { return safeData; }

    const lowerSearch = searchValue.toLowerCase();
    return safeData.filter((row) => columns.some((col) => {
      const value = row[col.accessor];
      return value && String(value).toLowerCase().includes(lowerSearch);
    }));
  }, [safeData, searchValue, searchable, columns, serverPagination]);

  const handleExport = () => {
    exportRecords(title, columns, filteredData);
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const renderCellValue = (row, column) => {
    const val = row[column.accessor];
    if (['statut', 'statut_display', 'status', 'status_display', 'etat', 'etat_display'].includes(column.accessor)
      || (['Statut', 'État'].includes(column.Header) && typeof val === 'boolean')) {
      let value = row[column.accessor.replace(/_display$/, '')] ?? val;
      if (typeof val === 'boolean') { value = val ? 'actif' : 'inactif'; }
      return <StatusBadge value={value} label={column.accessor.endsWith('_display') ? val : undefined} />;
    }
    if (column.Cell) {
      return column.Cell({ value: row[column.accessor], row: { original: row } });
    }
    return val !== undefined && val !== null ? val : '-';
  };

  return (
    <Card className="sis-data-table">
      {((title && showTitle) || searchable || exportable || onRefresh || onAdd || toolbarActions) && (
      <CardContent sx={{ borderBottom: 1, borderColor: 'divider', py: 2 }}>
        <Box sx={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2,
        }}
        >
          {title && showTitle && <Typography variant="h6" component="h2" fontWeight={600}>{title}</Typography>}
          <Box sx={{
            display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap', width: { xs: '100%', sm: 'auto' }, minWidth: 0,
          }}
          >
            {searchable && (
              <TextField
                placeholder="Rechercher..."
                label="Rechercher"
                value={serverPagination ? serverPagination.search : searchValue}
                onChange={(e) => {
                  if (serverPagination) {
                    serverPagination.onSearchChange(e.target.value);
                  } else {
                    setSearchValue(e.target.value);
                    setPage(0);
                  }
                }}
                size="small"
                sx={{ width: { xs: '100%', sm: 220 } }}
                slotProps={{
                  input: {
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon color="action" fontSize="small" />
                      </InputAdornment>
                    ),
                  },
                }}
              />
            )}
            {exportable && (
              <Button variant="outlined" startIcon={<DownloadIcon />} onClick={handleExport} size="medium">
                Exporter
              </Button>
            )}
            {onRefresh && (
              <Tooltip title="Actualiser">
                <IconButton aria-label="Actualiser" onClick={onRefresh}><RefreshIcon /></IconButton>
              </Tooltip>
            )}
            {onAdd && (
              <Button variant="contained" startIcon={<AddIcon />} onClick={onAdd}>{addButtonLabel}</Button>
            )}
          </Box>
          {toolbarActions && (
            <Box className="sis-table-actions" sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>{toolbarActions}</Box>
          )}
        </Box>
      </CardContent>
      )}

      {loading ? (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress size={40} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Chargement...</Typography>
        </Box>
      ) : (
        <>
          <TableContainer tabIndex={0} role="region" aria-label={`Tableau : ${title || 'données'}`}>
            <Table aria-label={title || 'Données'}>
              <TableHead>
                <TableRow>
                  {columns.map((column) => (
                    <TableCell key={column.accessor} sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
                      {column.Header}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredData.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={columns.length} align="center" sx={{ py: 6 }}>
                      <Typography variant="body1" color="text.secondary">{emptyMessage}</Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  (serverPagination ? filteredData : filteredData
                    .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage))
                    .map((row, rowIndex) => (
                      <TableRow
                        key={row.id || rowIndex}
                        hover
                        sx={{ cursor: onRowClick ? 'pointer' : 'default' }}
                        onClick={() => onRowClick && onRowClick({ original: row })}
                        tabIndex={onRowClick ? 0 : undefined}
                        onKeyDown={(event) => {
                          if (onRowClick && event.target === event.currentTarget && ['Enter', ' '].includes(event.key)) {
                            event.preventDefault();
                            onRowClick({ original: row });
                          }
                        }}
                      >
                        {columns.map((column) => (
                          <TableCell key={column.accessor}>{renderCellValue(row, column)}</TableCell>
                        ))}
                      </TableRow>
                    ))
                )}
              </TableBody>
            </Table>
          </TableContainer>

          <TablePagination
            component="div"
            count={serverPagination ? serverPagination.count : filteredData.length}
            page={serverPagination ? serverPagination.page : page}
            onPageChange={serverPagination ? (_, value) => serverPagination.onPageChange(value) : handleChangePage}
            rowsPerPage={serverPagination ? serverPagination.pageSize : rowsPerPage}
            onRowsPerPageChange={serverPagination
              ? event => serverPagination.onPageSizeChange(Number(event.target.value)) : handleChangeRowsPerPage}
            rowsPerPageOptions={[5, 10, 25, 50]}
            labelRowsPerPage="Lignes par page:"
            labelDisplayedRows={({ from, to, count }) => `${from}–${to} sur ${count}`}
          />
        </>
      )}
    </Card>
  );
};

SISDataTable.propTypes = {
  title: PropTypes.string.isRequired,
  showTitle: PropTypes.bool,
  toolbarActions: PropTypes.node,
  data: PropTypes.oneOfType([PropTypes.array, PropTypes.object]),
  columns: PropTypes.arrayOf(PropTypes.shape({
    Header: PropTypes.string.isRequired,
    accessor: PropTypes.string.isRequired,
    Cell: PropTypes.func,
  })).isRequired,
  loading: PropTypes.bool,
  onRowClick: PropTypes.func,
  onAdd: PropTypes.func,
  addButtonLabel: PropTypes.string,
  searchable: PropTypes.bool,
  exportable: PropTypes.bool,
  pageSize: PropTypes.number,
  emptyMessage: PropTypes.string,
  onRefresh: PropTypes.func,
  serverPagination: PropTypes.shape({
    page: PropTypes.number.isRequired,
    pageSize: PropTypes.number.isRequired,
    count: PropTypes.number.isRequired,
    search: PropTypes.string.isRequired,
    onPageChange: PropTypes.func.isRequired,
    onPageSizeChange: PropTypes.func.isRequired,
    onSearchChange: PropTypes.func.isRequired,
  }),
};

SISDataTable.defaultProps = {
  showTitle: true,
  toolbarActions: null,
  data: [],
  loading: false,
  onRowClick: null,
  onAdd: null,
  addButtonLabel: 'Ajouter',
  searchable: true,
  exportable: true,
  pageSize: 10,
  emptyMessage: 'Aucune donnée disponible',
  onRefresh: null,
  serverPagination: null,
};

export default SISDataTable;
