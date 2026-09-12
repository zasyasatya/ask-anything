export default function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-label="Ask Anything">
      <rect x="4" y="6" width="14" height="4.5" rx="2.25" transform="rotate(-35 4 6)" fill="#18181b" />
      <rect x="7.5" y="12.5" width="14" height="4.5" rx="2.25" transform="rotate(-35 7.5 12.5)" fill="#18181b" />
    </svg>
  );
}
