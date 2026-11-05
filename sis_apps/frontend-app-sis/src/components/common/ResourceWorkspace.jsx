import React from 'react';
import PropTypes from 'prop-types';
import PageHeader from './PageHeader';
import SectionNavigator from './SectionNavigator';

const ResourceWorkspace = ({ title, notice, children }) => (
  <>
    <PageHeader title={title} />
    {notice}
    <SectionNavigator
      label={`Gestion : ${title}`}
      sections={React.Children.toArray(children).map(resource => ({
        id: resource.props.resource,
        label: resource.props.title,
        content: React.cloneElement(resource, { showHeading: false }),
      }))}
    />
  </>
);

ResourceWorkspace.propTypes = {
  title: PropTypes.string.isRequired,
  notice: PropTypes.node,
  children: PropTypes.oneOfType([PropTypes.element, PropTypes.arrayOf(PropTypes.element)]).isRequired,
};
ResourceWorkspace.defaultProps = { notice: null };

export default ResourceWorkspace;
