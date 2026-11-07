export function ArrowIcon({ diagonal = false }: { diagonal?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d={diagonal ? "M6 18 18 6M6 6h12v12" : "M4 12h15m-6-6 6 6-6 6"}
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SparkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="32" height="32" viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <path d="M20 1c0 13-6 19-19 19 13 0 19 6 19 19 0-13 6-19 19-19C26 20 20 14 20 1Z" fill="currentColor" />
    </svg>
  );
}
