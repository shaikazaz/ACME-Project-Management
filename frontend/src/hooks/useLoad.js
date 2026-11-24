import { useEffect, useMemo, useState } from 'react';

/**
 * Loads data and cancels outdated requests.
 * @param {function(AbortSignal): Promise<any>} load Loader; memoize it.
 * @returns {{data: any, error: Error|null, loading: boolean, reload: Function}}
 *   The state. Earlier data stays available while new data loads.
 */
function useLoad(load) {
  const [version, setVersion] = useState(0);
  const key = useMemo(() => ({ load, version }), [load, version]);
  const [state, setState] = useState({ key: null, data: null, error: null });

  useEffect(() => {
    const controller = new AbortController();
    key.load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ key, data, error: null });
      },
      (error) => {
        if (!controller.signal.aborted) {
          setState((current) => ({ ...current, key, error }));
        }
      },
    );
    return () => controller.abort();
  }, [key]);

  const loading = state.key !== key;
  return {
    data: state.data,
    error: loading ? null : state.error,
    loading,
    reload: () => setVersion((current) => current + 1),
  };
}

export default useLoad;
