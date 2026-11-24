import { useMediaQuery } from 'react-responsive';

/**
 * Tells what kind of screen is used.
 * @returns {{isMobile: boolean, isCompact: boolean}} Mobile is below 768 pixels.
 *   Compact also includes tablets, below 1200 pixels.
 */
function useScreen() {
  const isMobile = useMediaQuery({ maxWidth: 767 });
  const isCompact = useMediaQuery({ maxWidth: 1199 });
  return { isMobile, isCompact };
}

export default useScreen;
