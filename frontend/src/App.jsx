import { useEffect, useState } from "react";
import { api } from "./api.js";
import { LayoutDashboard, FilePlus2, ListChecks, SlidersHorizontal, Plus, Cpu, Database } from "lucide-react";
import { Button } from "./components/ui/Button.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Upload from "./pages/Upload.jsx";
import Claims from "./pages/Claims.jsx";
import Decision from "./pages/Decision.jsx";
import Diagnostics from "./pages/Diagnostics.jsx";
import Admin from "./pages/Admin.jsx";

export function navigate(path) { window.location.hash = path; }

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash.replace(/^#/, "") || "/";
}

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, match: (p) => p === "/" },
  { to: "/new", label: "New claim", icon: FilePlus2, match: (p) => p === "/new" },
  { to: "/claims", label: "Claims", icon: ListChecks, match: (p) => p.startsWith("/claims") },
  { to: "/admin", label: "Admin", icon: SlidersHorizontal, match: (p) => p === "/admin" },
];

const TITLES = [
  [/^\/$/, "Operations center", "Workspace"],
  [/^\/new$/, "New claim", "Workspace"],
  [/^\/claims$/, "Claims", "Workspace"],
  [/^\/claims\/\d+\/diagnostics$/, "Diagnostics", "Claim"],
  [/^\/claims\/\d+$/, "Decision", "Claim"],
  [/^\/admin$/, "Admin", "Configuration"],
];
function titleFor(path) { for (const [re, t, c] of TITLES) if (re.test(path)) return [t, c]; return ["Not found", ""]; }

export default function App() {
  const path = useHashRoute();
  const [status, setStatus] = useState({ llm: "…", db: "…", count: null });

  useEffect(() => {
    api.health().then((h) => setStatus((s) => ({ ...s,
      llm: (h.llm_mode || "offline").toUpperCase(),
      db: (h.database || "").includes("postgres") ? "POSTGRES" : "SQLITE" }))).catch(() => {});
    api.listClaims().then((c) => setStatus((s) => ({ ...s, count: c.length }))).catch(() => {});
  }, [path]);

  let view;
  const mDiag = path.match(/^\/claims\/(\d+)\/diagnostics$/);
  const mDetail = path.match(/^\/claims\/(\d+)$/);
  if (path === "/") view = <Dashboard />;
  else if (path === "/new") view = <Upload />;
  else if (path === "/claims") view = <Claims />;
  else if (path === "/admin") view = <Admin />;
  else if (mDiag) view = <Diagnostics id={mDiag[1]} />;
  else if (mDetail) view = <Decision id={mDetail[1]} />;
  else view = (
    <div className="mx-auto max-w-md rounded-2xl border border-line bg-panel p-10 text-center">
      <h2 className="font-display text-2xl">Page not found</h2>
      <p className="mt-2 text-ink-dim">That route doesn’t exist.</p>
      <Button variant="gold" className="mt-5" onClick={() => navigate("/new")}>New claim</Button>
    </div>
  );

  const [title, crumb] = titleFor(path);
  const llmOn = status.llm === "OPENAI" || status.llm === "ANTHROPIC";

  return (
    <div className="min-h-screen grid grid-cols-[480px_1fr] max-[900px]:grid-cols-1">
      {/* sidebar */}
      <aside className="sticky top-0 h-screen border-r border-line bg-panel/60 backdrop-blur flex flex-col max-[900px]:hidden">
        <a href="#/" className="px-6 pt-7 pb-6 block">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-gold-2 to-gold text-base text-lg font-bold shadow-lg">◈</span>
            <span className="font-display text-2xl font-semibold tracking-tight">Claims Manager</span>
          </div>
          <p className="mt-1.5 pl-0.5 text-xs uppercase tracking-[0.18em] text-ink-mut">Adjudication platform</p>
        </a>
        <nav className="flex-1 px-3">
          <p className="px-3 pb-2 pt-3 text-xs font-semibold uppercase tracking-wider text-ink-mut">Workspace</p>
          {NAV.map(({ to, label, icon: Icon, match }) => {
            const active = match(path);
            return (
              <a key={to} href={"#" + to}
                className={"group flex items-center gap-3 rounded-xl px-3 py-2.5 text-base font-medium transition mb-0.5 " +
                  (active ? "bg-gold/12 text-gold-2 shadow-[inset_0_0_0_1px_rgba(216,181,103,0.18)]" : "text-ink-dim hover:bg-line/40 hover:text-ink")}>
                <Icon className={"h-[18px] w-[18px] " + (active ? "text-gold" : "text-ink-mut group-hover:text-ink")} strokeWidth={2} />
                {label}
              </a>
            );
          })}
        </nav>
        <div className="border-t border-line p-4 space-y-2 text-xs">
          <div className="flex items-center gap-2 text-ink-dim"><Cpu className="h-3.5 w-3.5" /><span className={"h-1.5 w-1.5 rounded-full " + (llmOn ? "bg-gold shadow-[0_0_8px] shadow-gold" : "bg-ink-mut")} />Engine · <b className="text-ink">{status.llm}</b></div>
          <div className="flex items-center gap-2 text-ink-dim"><Database className="h-3.5 w-3.5" /><span className="h-1.5 w-1.5 rounded-full bg-approve" />DB · <b className="text-ink">{status.db}</b></div>
        </div>
      </aside>

      {/* content */}
      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-line bg-ground/80 px-6 py-4 backdrop-blur-xl">
          <div className="min-w-0">
            {crumb && <span className="text-xs font-semibold uppercase tracking-wider text-ink-mut">{crumb} /</span>}
            <h1 className="font-display text-2xl font-medium tracking-tight truncate">{title}</h1>
          </div>
          <div className="flex items-center gap-2.5">
            <span className="hidden items-center gap-2 rounded-full border border-line bg-panel px-3 py-1.5 text-xs text-ink-dim sm:inline-flex">
              <span className={"h-1.5 w-1.5 rounded-full " + (llmOn ? "bg-gold shadow-[0_0_8px] shadow-gold" : "bg-ink-mut")} />Engine · <b className="text-ink">{status.llm}</b></span>
            {status.count != null && <span className="hidden items-center gap-2 rounded-full border border-line bg-panel px-3 py-1.5 text-xs text-ink-dim md:inline-flex">Claims · <b className="text-ink">{status.count}</b></span>}
            <Button variant="gold" size="md" onClick={() => navigate("/new")}><Plus className="h-4 w-4" />New claim</Button>
          </div>
        </header>
        <main className="w-full px-8 py-7 max-[900px]:px-5">{view}</main>
      </div>
    </div>
  );
}
