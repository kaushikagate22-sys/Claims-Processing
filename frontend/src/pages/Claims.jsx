import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { navigate } from "../App.jsx";
import { money, dateTime, DECISION_TONE, DECISION_LABEL } from "../lib/format.js";
import { Card } from "../components/ui/Card.jsx";
import { Badge } from "../components/ui/Badge.jsx";
import { Input } from "../components/ui/Field.jsx";
import { Skeleton } from "../components/ui/Skeleton.jsx";
import { Search, ArrowRight } from "lucide-react";

const FILTERS = [
  { key: "ALL", label: "All" },
  { key: "APPROVED", label: "Approved" },
  { key: "HOLD", label: "Hold" },
  { key: "ESCALATE", label: "Escalate" },
  { key: "REJECTED", label: "Rejected" },
];

export default function Claims() {
  const [claims, setClaims] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("ALL");

  useEffect(() => { api.listClaims().then(setClaims).catch((e) => setError(e.message)); }, []);

  const rows = useMemo(() => {
    if (!claims) return [];
    const needle = q.trim().toLowerCase();
    return claims.filter((c) => {
      if (filter !== "ALL" && c.decision !== filter) return false;
      if (!needle) return true;
      return [c.id, c.claim_type, c.claimant_name, c.decision].join(" ").toLowerCase().includes(needle);
    });
  }, [claims, q, filter]);

  if (error) return <div className="rounded-xl border border-reject/30 bg-reject/10 p-4 text-reject">{error}</div>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-mut" />
          <Input className="pl-9" placeholder="Search by id, type, claimant…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex gap-1.5">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={"rounded-lg px-3 py-2 text-sm font-medium transition " +
                (filter === f.key ? "bg-gold/15 text-gold-2" : "text-ink-dim hover:bg-line/40 hover:text-ink")}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <Card className="overflow-hidden">
        {!claims ? (
          <div className="space-y-2 p-5">{[0,1,2,3,4].map(i => <Skeleton key={i} className="h-12" />)}</div>
        ) : rows.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <p className="font-display text-xl">No claims found</p>
            <p className="mt-1 text-ink-dim">{claims.length === 0 ? "Process your first claim to see it here." : "Try a different search or filter."}</p>
          </div>
        ) : (
          <table className="w-full text-base">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-mut">
              <tr>
                <th className="px-5 py-3 font-semibold">Claim</th>
                <th className="px-5 py-3 font-semibold">Type</th>
                <th className="px-5 py-3 font-semibold">Decision</th>
                <th className="px-5 py-3 text-right font-semibold">Claimed</th>
                <th className="px-5 py-3 text-right font-semibold">Payout</th>
                <th className="px-5 py-3 font-semibold">When</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} onClick={() => navigate(`/claims/${c.id}`)}
                  className="group cursor-pointer border-b border-line last:border-0 transition hover:bg-line/30">
                  <td className="px-5 py-3.5">
                    <div className="font-medium">{c.claimant_name || `Claim #${c.id}`}</div>
                    <div className="font-mono text-xs text-ink-mut">#{c.id}</div>
                  </td>
                  <td className="px-5 py-3.5 capitalize text-ink-dim">{(c.claim_type || "—").replace(/_/g, " ")}</td>
                  <td className="px-5 py-3.5"><Badge tone={DECISION_TONE[c.decision] || "muted"}>{DECISION_LABEL[c.decision] || "—"}</Badge></td>
                  <td className="px-5 py-3.5 text-right font-mono tabular-nums text-ink-dim">{money(c.claim_amount)}</td>
                  <td className="px-5 py-3.5 text-right font-mono tabular-nums">{money(c.approved_amount)}</td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-sm text-ink-dim">{dateTime(c.created_at)}</td>
                  <td className="px-5 py-3.5"><ArrowRight className="h-4 w-4 text-ink-mut opacity-0 transition group-hover:opacity-100" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
