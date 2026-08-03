import { cn } from "@/lib/utils";

interface NovaLogoProps {
  className?: string;
  title?: string;
}

/** The "ether engine" brand mark: a white disc with a dark "e". */
export function NovaLogo({ className, title = "ether engine" }: NovaLogoProps) {
  return (
    <svg
      viewBox="0 0 240 240"
      fill="none"
      role="img"
      aria-label={title}
      className={cn("size-8", className)}
    >
      <circle cx="120" cy="120" r="112" fill="#ffffff" />
      <g
        fill="none"
        stroke="#0d0d0d"
        strokeWidth="30"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M191 94 A76 76 0 1 0 178 169" />
        <path d="M50 122 C 92 106, 150 110, 190 120" />
      </g>
    </svg>
  );
}
