import React, { useId, useState } from 'react';
import PropTypes from 'prop-types';
import { Tab, Tabs } from '@mui/material';

const RecordsTabs = ({ label, panels }) => {
  const id = useId();
  const [selected, setSelected] = useState(0);
  return (
    <>
      <Tabs className="sis-records-tabs" value={selected} onChange={(_, value) => setSelected(value)} aria-label={label}>
        {panels.map((panel, index) => (
          <Tab key={panel.label} label={panel.label} id={`${id}-tab-${index}`} aria-controls={`${id}-panel-${index}`} />
        ))}
      </Tabs>
      {panels.map((panel, index) => (
        <div
          key={panel.label}
          className="sis-records-panel"
          role="tabpanel"
          id={`${id}-panel-${index}`}
          aria-labelledby={`${id}-tab-${index}`}
          hidden={selected !== index}
          tabIndex={0}
        >
          {selected === index && panel.content}
        </div>
      ))}
    </>
  );
};

RecordsTabs.propTypes = {
  label: PropTypes.string.isRequired,
  panels: PropTypes.arrayOf(PropTypes.shape({
    label: PropTypes.string.isRequired,
    content: PropTypes.node.isRequired,
  })).isRequired,
};

export default RecordsTabs;
