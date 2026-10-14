// The Bitcoin mark: an orange disc with a slanted "B" crossed by two short strokes.
export default function BitcoinLogo({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Bitcoin">
      <circle cx="32" cy="32" r="32" fill="#F7931A" />
      <g transform="rotate(14 32 32)" fill="#fff">
        <rect x="26" y="12" width="3.5" height="8" rx="1" />
        <rect x="33" y="12" width="3.5" height="8" rx="1" />
        <rect x="26" y="44" width="3.5" height="8" rx="1" />
        <rect x="33" y="44" width="3.5" height="8" rx="1" />
        <text x="32" y="45" textAnchor="middle" fontSize="34" fontWeight="800"
              fontFamily="Arial, Helvetica, sans-serif">B</text>
      </g>
    </svg>
  );
}
