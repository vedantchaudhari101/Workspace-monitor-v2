/**
 * Small stroke icon set drawn for this product (24px grid, 1.6 stroke).
 */

const paths = {
  live: (
    <>
      <circle cx="12" cy="12" r="2.2" />
      <path d="M7.8 16.2a6 6 0 0 1 0-8.4M16.2 7.8a6 6 0 0 1 0 8.4M5 19a10 10 0 0 1 0-14M19 5a10 10 0 0 1 0 14" />
    </>
  ),
  analytics: <path d="M4 19h16M6 16v-5M10 16V8M14 16v-3M18 16V6" />,
  recommendations: (
    <>
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
      <path d="M12 8.5 13.2 11l2.3 1-2.3 1L12 15.5 10.8 13l-2.3-1 2.3-1z" />
    </>
  ),
  explorer: (
    <>
      <rect x="3.5" y="4.5" width="17" height="15" rx="1.5" />
      <path d="M3.5 10h17M10 10v9.5M7 7.2h.01M10 7.2h.01" />
      <rect x="12.5" y="12.5" width="5" height="4" rx=".8" />
    </>
  ),
  insights: <path d="M3 12h4l2.5-6 5 12 2.5-6h4" />,
  upload: (
    <>
      <path d="M12 15V4M7.5 8.5 12 4l4.5 4.5" />
      <path d="M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15" />
    </>
  ),
  stop: <rect x="6.5" y="6.5" width="11" height="11" rx="1.5" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  download: (
    <>
      <path d="M12 4v11M7.5 10.5 12 15l4.5-4.5" />
      <path d="M4 17v1.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V17" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 11a8 8 0 0 0-14.3-4.7L4 8" />
      <path d="M4 4v4h4M4 13a8 8 0 0 0 14.3 4.7L20 16" />
      <path d="M20 20v-4h-4" />
    </>
  ),
  grid: (
    <>
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="4" width="6" height="6" rx="1" />
      <rect x="4" y="14" width="6" height="6" rx="1" />
      <rect x="14" y="14" width="6" height="6" rx="1" />
    </>
  ),
  map: (
    <>
      <path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z" />
      <path d="M9 4v13.5M15 6.5V20" />
    </>
  ),
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  logout: (
    <>
      <path d="M14 4h4.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H14" />
      <path d="M10 8l-4 4 4 4M6 12h10" />
    </>
  ),
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  arrowLeft: <path d="M19 12H5M11 6l-6 6 6 6" />,
  film: (
    <>
      <rect x="3.5" y="5" width="17" height="14" rx="1.5" />
      <path d="M7 5v14M17 5v14M3.5 9.5H7M3.5 14.5H7M17 9.5h3.5M17 14.5h3.5" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
};

export default function Icon({ name, size = 18, className, title }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
    >
      {title && <title>{title}</title>}
      {paths[name]}
    </svg>
  );
}
