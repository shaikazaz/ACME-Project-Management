import { useState } from 'react';

/**
 * Keeps a list of departments that can grow while a form is open.
 * @param {Object[]} initial The departments.
 * @returns {Object} departments, adding, open, close and add.
 */
function useDepartments(initial) {
  const [departments, setDepartments] = useState(initial);
  const [adding, setAdding] = useState(false);
  return {
    departments,
    adding,
    open: () => setAdding(true),
    close: () => setAdding(false),
    add: (department) => {
      setDepartments((current) => [...current, department]);
      setAdding(false);
    },
  };
}

export default useDepartments;
