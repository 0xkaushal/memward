const STATUS_STYLES = {
  pending_review: 'badge badge-pending',
  approved:       'badge badge-approved',
  archived:       'badge badge-archived',
}

export function StatusBadge({ status }) {
  return (
    <span className={STATUS_STYLES[status] ?? 'badge badge-archived'}>
      {status.replace('_', ' ')}
    </span>
  )
}

export function Badge({ className, children }) {
  return <span className={`badge ${className}`}>{children}</span>
}
