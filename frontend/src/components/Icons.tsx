import type { SVGProps } from "react";

/**
 * Small, dependency-free icon set with a single consistent stroke weight.
 * Replaces emoji glyphs so document types, sources and status share one visual language.
 */

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 20, ...rest }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...rest,
  };
}

/** Deepwell mark — a drop of water over the well's depth. */
export function WellMark({ size = 24, ...rest }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" {...rest}>
      <path
        d="M12 3c-3.6 4.6-6 8.1-6 11.1a6 6 0 0 0 12 0c0-3-2.4-6.5-6-11.1z"
        fill="currentColor"
      />
    </svg>
  );
}

export function PdfIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 2h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
      <path d="M14 2v4h4" />
      <path d="M8.5 15.5c1.5 0 2.2-1 2.8-2.4.6-1.4 1.2-2.6 2.8-2.6" strokeWidth={1.3} />
    </svg>
  );
}

export function ArticleIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M5 3h11a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z" />
      <path d="M8 7h7M8 11h7M8 15h4" />
    </svg>
  );
}

export function WebIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z" />
    </svg>
  );
}

export function FileIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M6 2h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
      <path d="M14 2v4h4" />
    </svg>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.2-3.2" />
    </svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

export function ArrowUpIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M12 19V5" />
      <path d="m6 11 6-6 6 6" />
    </svg>
  );
}

export function ExternalIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M14 4h6v6" />
      <path d="M20 4 10 14" />
      <path d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4" />
    </svg>
  );
}

export function GridIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

export function ListIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01" />
    </svg>
  );
}

export function ArrowLeftIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M19 12H5" />
      <path d="m12 19-7-7 7-7" />
    </svg>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  );
}

// --- Category icons ---
export function WrenchIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M14.5 5.5a3.5 3.5 0 0 0 4.6 4.6l-7 7a3.5 3.5 0 0 1-4.6-4.6l7-7z" />
      <path d="m5 19 3-3" />
    </svg>
  );
}

export function HeartPulseIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M19 14c1.5-1.5 3-3.2 3-5.5A3.5 3.5 0 0 0 12 5 3.5 3.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7z" />
      <path d="M3.5 12h4l1.5-3 2 5 1.5-2h4" />
    </svg>
  );
}

export function CompassIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5 5-2z" />
    </svg>
  );
}

export function LeafIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M4 20c0-8 6-14 16-14 0 10-6 16-14 16" />
      <path d="M4 20c3-5 7-8 12-9" />
    </svg>
  );
}

export function AtomIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
      <ellipse cx="12" cy="12" rx="10" ry="4.2" />
      <ellipse cx="12" cy="12" rx="10" ry="4.2" transform="rotate(60 12 12)" />
      <ellipse cx="12" cy="12" rx="10" ry="4.2" transform="rotate(120 12 12)" />
    </svg>
  );
}

export function FolderIcon(props: IconProps) {
  return (
    <svg {...base(props)}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}

/** Icon + tint for a top-level category. */
export function categoryMeta(category: string): { Icon: (p: IconProps) => JSX.Element; tint: string } {
  switch (category) {
    case "Device Repair":
      return { Icon: WrenchIcon, tint: "bg-data-slate/12 text-data-slate" };
    case "Health & Medicine":
      return { Icon: HeartPulseIcon, tint: "bg-data-clay/12 text-data-clay" };
    case "Emergency Preparedness & Survival":
      return { Icon: CompassIcon, tint: "bg-data-gold/12 text-data-gold" };
    case "Home, Garden & Self-Reliance":
      return { Icon: LeafIcon, tint: "bg-data-moss/12 text-data-moss" };
    case "Science & Mathematics":
      return { Icon: AtomIcon, tint: "bg-accent-soft text-accent-ink" };
    default:
      return { Icon: FolderIcon, tint: "bg-surface-sunk text-ink-faint" };
  }
}

export function docIconFor(type: string) {
  if (type === "pdf") return PdfIcon;
  if (type === "web") return WebIcon;
  if (type === "zim") return ArticleIcon;
  return FileIcon;
}
