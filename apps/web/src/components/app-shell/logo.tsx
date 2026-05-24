interface Props {
  className?: string;
}

export function Logo({ className }: Props) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M4 18 L12 4 L20 18" />
      <path d="M7.5 13 L16.5 13" />
    </svg>
  );
}
