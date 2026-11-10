import React from 'react';
import PropTypes from 'prop-types';
import { Button } from '@mui/material';

const CollectionPagination = ({
  data, page, setPage, label = 'Résultats', disabled = false,
  previousLabel = 'Page précédente', nextLabel = 'Page suivante',
}) => {
  if (!data) { return null; }
  const multiple = Boolean(data.previous || data.next || page > 1);
  if (!data.count && !multiple) { return null; }
  return (
    <nav aria-label={`Pagination — ${label}`} className="sis-collection-pagination">
      {multiple && (
        <Button type="button" variant="outlined" disabled={disabled || page <= 1} onClick={() => setPage(page - 1)}>
          {previousLabel}
        </Button>
      )}
      <span className="sis-collection-pagination__summary" aria-live="polite">
        {multiple ? `Page ${page} — ` : ''}{data.count} résultat(s)
      </span>
      {multiple && (
        <Button type="button" variant="outlined" disabled={disabled || !data.next} onClick={() => setPage(page + 1)}>
          {nextLabel}
        </Button>
      )}
    </nav>
  );
};
CollectionPagination.propTypes = {
  data: PropTypes.shape({ count: PropTypes.number.isRequired, previous: PropTypes.string, next: PropTypes.string }),
  page: PropTypes.number.isRequired,
  setPage: PropTypes.func.isRequired,
  label: PropTypes.string,
  disabled: PropTypes.bool,
  previousLabel: PropTypes.string,
  nextLabel: PropTypes.string,
};
export default CollectionPagination;
