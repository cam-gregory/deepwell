import { Link, useLocation } from "react-router-dom";
import { WellMark } from "./Icons";

const ROUTE_LOADERS = {
  "/": () => import("../pages/Ask"),
  "/library": () => import("../pages/Library"),
  "/dashboard": () => import("../pages/Dashboard"),
  "/debug": () => import("../pages/Debug"),
  "/add": () => import("../pages/Add"),
} as const;

const LINKS = [
  { to: "/", label: "Ask", variant: "primary" },
  { to: "/library", label: "Library", variant: "primary" },
  { to: "/dashboard", label: "Dashboard", variant: "primary" },
  { to: "/add", label: "Add data", variant: "secondary" },
  { to: "/debug", label: "Debug", variant: "secondary" },
] as const;

export default function Nav() {
  const { pathname } = useLocation();

  const prefetchRoute = (to: string) => {
    const loader = ROUTE_LOADERS[to as keyof typeof ROUTE_LOADERS];
    if (loader) void loader();
  };

  return (
    <header className="sticky top-0 z-20 mb-10 border-b border-line/80 bg-paper/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-4">
        <Link to="/" className="group flex items-center gap-3 no-underline" onMouseEnter={() => prefetchRoute("/")}>
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent text-surface shadow-card transition-transform duration-300 ease-spring group-hover:-translate-y-0.5">
            <WellMark size={18} />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-display text-[22px] font-semibold tracking-[-0.01em] text-ink">Deepwell</span>
            <span className="mt-1 text-[10px] uppercase tracking-[0.22em] text-ink-faint">
              Draw from a world of knowledge
            </span>
          </span>
        </Link>

        <nav className="flex flex-wrap items-center justify-end gap-1.5 text-sm">
          {LINKS.map(({ to, label, variant }) => {
            const isActive = pathname === to;
            const isPrimary = variant === "primary";

            return (
              <Link
                key={to}
                to={to}
                aria-current={isActive ? "page" : undefined}
                onMouseEnter={() => prefetchRoute(to)}
                onFocus={() => prefetchRoute(to)}
                className={[
                  "relative inline-flex items-center rounded-lg px-3 py-2 font-medium no-underline transition-colors duration-200",
                  isPrimary
                    ? isActive
                      ? "bg-ink text-surface"
                      : "text-ink-soft hover:bg-ink/[0.06] hover:text-ink"
                    : isActive
                      ? "text-accent-ink"
                      : "text-ink-faint hover:text-accent-ink",
                ].join(" ")}
              >
                {label}
                {!isPrimary && (
                  <span
                    className="ml-1.5 h-1.5 w-1.5 rounded-full bg-data-gold/80"
                    title="Admin tool"
                    aria-label="Admin tool"
                  />
                )}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
