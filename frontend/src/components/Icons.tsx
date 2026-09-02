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

export function docIconFor(type: string) {
  if (type === "pdf") return PdfIcon;
  if (type === "web") return WebIcon;
  if (type === "zim") return ArticleIcon;
  return FileIcon;
}
