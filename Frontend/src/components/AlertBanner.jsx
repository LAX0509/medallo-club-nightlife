export function AlertBanner({ nivel = "bajo", children }) {
  return <div className={`alert-banner nivel-${nivel}`}>{children}</div>;
}
