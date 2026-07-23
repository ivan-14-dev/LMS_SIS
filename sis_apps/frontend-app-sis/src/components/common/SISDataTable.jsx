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
}) => {
  const [searchValue, setSearchValue] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(initialPageSize);

  // Ensure data is always an array
  const safeData = useMemo(() => {
    if (Array.isArray(data)) return data;
    if (data?.results && Array.isArray(data.results)) return data.results;
    return [];
  }, [data]);

  const filteredData = useMemo(() => {
    if (!searchable || !searchValue) return safeData;
    
    const lowerSearch = searchValue.toLowerCase();
    return safeData.filter((row) =>
      columns.some((col) => {
        const value = row[col.accessor];
        return value && String(value).toLowerCase().includes(lowerSearch);
      })
    );
  }, [safeData, searchValue, searchable, columns]);

  const handleExport = () => {
    const headers = columns.map((col) => col.Header).join(',');
    const rows = filteredData.map((row) =>
      columns.map((col) => {
        const val = row[col.accessor];
        return '"' + (val !== undefined ? val : '') + '"';
      }).join(',')
    );
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = title.toLowerCase().replace(/\s+/g, '_') + '.csv';
    a.click();
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const renderCellValue = (row, column) => {
    if (column.Cell) {
      return column.Cell({ value: row[column.accessor], row: { original: row } });
    }
    const val = row[column.accessor];
    return val !== undefined && val !== null ? val : '-';
  };

  return (
    <Card>
      <CardContent sx={{ borderBottom: 1, borderColor: 'divider', py: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
          <Typography variant="h6" fontWeight={600}>{title}</Typography>
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
            {searchable && (
              <TextField
                placeholder="Rechercher..."
                value={searchValue}
                onChange={(e) => { setSearchValue(e.target.value); setPage(0); }}
                size="small"
                sx={{ minWidth: 220 }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon color="action" fontSize="small" />
                    </InputAdornment>
                  ),
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
                <IconButton onClick={onRefresh} size="small"><RefreshIcon /></IconButton>
              </Tooltip>
            )}
            {onAdd && (
              <Button variant="contained" startIcon={<AddIcon />} onClick={onAdd}>{addButtonLabel}</Button>
            )}
          </Box>
        </Box>
      </CardContent>

      {loading ? (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress size={40} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Chargement...</Typography>
        </Box>
      ) : (
        <>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  {columns.map((column, index) => (
                    <TableCell key={index} sx={{ fontWeight: 600, bgcolor: 'grey.50', whiteSpace: 'nowrap' }}>
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
                  filteredData
                    .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                    .map((row, rowIndex) => (
                      <TableRow 
                        key={row.id || rowIndex}
                        hover
                        sx={{ cursor: onRowClick ? 'pointer' : 'default' }}
                        onClick={() => onRowClick && onRowClick({ original: row })}
                      >
                        {columns.map((column, colIndex) => (
                          <TableCell key={colIndex}>{renderCellValue(row, column)}</TableCell>
                        ))}
                      </TableRow>
                    ))
                )}
              </TableBody>
            </Table>
          </TableContainer>

          <TablePagination
            component="div"
            count={filteredData.length}
            page={page}
            onPageChange={handleChangePage}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={handleChangeRowsPerPage}
            rowsPerPageOptions={[5, 10, 25, 50]}
            labelRowsPerPage="Lignes par page:"
            labelDisplayedRows={({ from, to, count }) => 'Showing ' + from + ' - ' + to + ' of ' + count + '.'}
          />
        </>
      )}
    </Card>
  );
};

SISDataTable.propTypes = {
  title: PropTypes.string.isRequired,
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
};

SISDataTable.defaultProps = {
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
};

export default SISDataTable;
