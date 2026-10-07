/** Loading, empty and error states with a clear next step. */

import Icon from "../ui/Icon";

export function EmptyState({ title, children, action, className = "" }) {
  return (
    <div className={`state ${className}`}>
      <div className="state-title">{title}</div>
      {children && <div className="small">{children}</div>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "Couldn't load this data" }) {
  return (
    <div className="state state-error" role="alert">
      <div className="state-title">{title}</div>
      <div className="small">{error?.message || "Something went wrong while talking to the server."}</div>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          <Icon name="refresh" /> Retry
        </button>
      )}
    </div>
  );
}

export function Skeleton({ height = 16, width = "100%", style }) {
  return <div className="skeleton" style={{ height, width, ...style }} aria-hidden="true" />;
}

export function Notice({ tone = "info", children }) {
  return (
    <div className={`notice ${tone === "warn" ? "notice-warn" : tone === "error" ? "notice-error" : ""}`} role={tone === "error" ? "alert" : "status"}>
      <Icon name="info" size={16} />
      <div>{children}</div>
    </div>
  );
}
