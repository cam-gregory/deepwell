import { Link, useLocation } from "react-router-dom";

const ROUTE_LOADERS = {
  "/": () => import("../pages/Ask"),
  "/library": () => import("../pages/Library"),
  "/debug": () => import("../pages/Debug"),
  "/add": () => import("../pages/Add"),
} as const;

const LINKS = [
  { to: "/", label: "Ask", variant: "primary" },
  { to: "/library", label: "Library", variant: "primary" },
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
    <header className="sticky top-0 z-20 mb-8 border-b border-slate-200/80 bg-slate-100/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <div className="text-xl font-semibold tracking-tight text-slate-900">Deepwell</div>
            <div className="text-[11px] uppercase tracking-[0.12em] text-slate-500">
              Draw from a world of knowledge
            </div>
          </div>
        </div>

        <nav className="flex flex-wrap items-center justify-end gap-3 text-sm">
          {LINKS.map(({ to, label, variant }) => {
            const isActive = pathname === to;
            const isPrimary = variant === "primary";

            return (
              <Link
                key={to}
                to={to}
                onMouseEnter={() => prefetchRoute(to)}
                onFocus={() => prefetchRoute(to)}
                className={[
                  "inline-flex items-center rounded-full border px-3.5 py-2 transition-all no-underline",
                  isPrimary
                    ? isActive
                      ? "border-slate-900 bg-slate-900 text-white shadow-sm"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                    : isActive
                      ? "border-amber-400 bg-amber-100 text-amber-900"
                      : "border-dashed border-amber-200 bg-amber-50/70 text-amber-800 hover:border-amber-300 hover:bg-amber-100",
                ].join(" ")}
              >
                {label}
                {!isPrimary && (
                  <span className="ml-2 rounded-full bg-amber-200/80 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-900">
                    Admin
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
