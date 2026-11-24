import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

export const PAGE_SIZE = 10;

/**
 * Keeps list filters, sorting and paging in the address, so they survive a
 * refresh and can be shared as a link.
 * @param {string[]} names Filter names; keep the same array between renders.
 * @param {string} defaultSort The initial sort field.
 * @param {'asc'|'desc'} [defaultOrder] The initial order.
 * @returns {Object} filters, sort, order, page, request values and actions.
 */
function useListParams(names, defaultSort, defaultOrder = 'asc') {
  const [params, setParams] = useSearchParams();
  const query = params.toString();
  const sort = params.get('sort') ?? defaultSort;
  const given = params.get('order');
  const order = ['asc', 'desc'].includes(given) ? given : defaultOrder;
  const page = Math.max(0, Number.parseInt(params.get('page'), 10) || 0);

  const filters = useMemo(() => {
    const current = new URLSearchParams(query);
    return Object.fromEntries(names.map((name) => [name, current.get(name) ?? '']));
  }, [query, names]);

  const requestParams = useMemo(() => ({
    ...filters, sort, order, limit: PAGE_SIZE, offset: page * PAGE_SIZE,
  }), [filters, sort, order, page]);

  // Any change other than paging goes back to the first page.
  const update = useCallback((changes) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      Object.entries({ page: '', ...changes }).forEach(([name, value]) => {
        if (value === '' || value === null) next.delete(name);
        else next.set(name, value);
      });
      return next;
    }, { replace: true });
  }, [setParams]);

  return {
    filters,
    sort,
    order,
    page,
    requestParams,
    update,
    isFiltered: names.some((name) => filters[name]),
    clear: () => setParams({}, { replace: true }),
    setPage: (next) => update({ page: next === 0 ? '' : String(next) }),
    toggleSort: (field) => update({
      sort: field,
      order: field === sort && order === 'asc' ? 'desc' : 'asc',
    }),
  };
}

export default useListParams;
