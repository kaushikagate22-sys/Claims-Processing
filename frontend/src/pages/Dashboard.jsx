import { useEffect, useState } from "react";
import { api } from "../api.js";
import { navigate } from "../App.jsx";
import { money, DECISION_LABEL } from "../lib/format.js";
import { Card, CardHeader, CardTitle, CardBody } from "../components/ui/Card.jsx";
import { Skeleton } from "../components/ui/Skeleton.jsx";
import { FileStack, CheckCircle2, AlertTriangle, IndianRupee, TrendingUp } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, Tooltip, BarChart, Bar } from "recharts";

const DEC_COLOR = { APPROVED: "#46C08A", HOLD: "#E2A63E", ESCALATE: "#5E8DF0", REJECTED: "#E76A60" };

function Kpi({ label, value, sub, icon: Icon, accent, onClick }) {
  return (
    <button onClick={onClick} className="group text-left rounded-2xl border border-line bg-panel/80 p-5 transition hover:border-gold/30 hover:-translate-y-0.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-ink-mut">{label}</span>
        <span className="grid h-9 w-9 place-items-center rounded-xl border border-line" style={{ color: accent }}><Icon className="h-[18px] w-[18px]" /></span>
      </div>
      <div className="mt-3 font-display text-4xl leading-none font-semibold tracking-tight">{value}</div>
      <div className="mt-2 text-sm text-ink-dim">{sub}</div>
    </button>
  );
}

function TipBox({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line-2 bg-raised px-3 py-2 text-sm shadow-xl">
      <div className="text-ink-mut">{label}</div>
      <div className="font-semibold text-ink">{payload[0].value}</div>
    </div>
  );
}

export default function Dashboard() {
  const [s, setS] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.getStats().then(setS).catch((e) => setError(e.message)); }, []);

  if (error) return <div className="rounded-xl border border-reject/30 bg-reject/10 p-4 text-reject">{error}</div>;
  if (!s) return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-5">{[0,1,2,3].map(i => <Skeleton key={i} className="h-32" />)}</div>
      <div className="grid grid-cols-2 gap-6 max-[820px]:grid-cols-1"><Skeleton className="h-72" /><Skeleton className="h-72" /></div>
    </div>
  );

  const d = s.by_decision || {};
  const approved = d.APPROVED || 0;
  const attention = (d.HOLD || 0) + (d.ESCALATE || 0) + (d.REJECTED || 0);
  const pie = Object.entries(d).map(([k, v]) => ({ name: DECISION_LABEL[k] || k, value: v, key: k }));
  const perDay = (s.per_day || []).map((x) => ({ day: (x.date || "").split(" ")[0], count: x.count }));
  const types = Object.entries(s.by_type || {}).sort((a, b) => b[1] - a[1]).map(([name, count]) => ({ name, count }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-5">
        <Kpi label="Total claims" value={s.total} sub={`${s.today_count || 0} processed today`} icon={FileStack} accent="#D8B567" onClick={() => navigate("/claims")} />
        <Kpi label="Approved" value={approved} sub={`${s.total ? Math.round((approved / s.total) * 100) : 0}% of all claims`} icon={CheckCircle2} accent="#46C08A" onClick={() => navigate("/claims")} />
        <Kpi label="Needs attention" value={attention} sub="Hold · Escalate · Reject" icon={AlertTriangle} accent="#E76A60" onClick={() => navigate("/claims")} />
        <Kpi label="Total payout" value={money(s.total_payout)} sub={`of ${money(s.total_claimed)} claimed`} icon={IndianRupee} accent="#D8B567" onClick={() => {}} />
      </div>

      <div className="grid grid-cols-2 gap-6 max-[820px]:grid-cols-1">
        <Card>
          <CardHeader><CardTitle>Claims by decision</CardTitle></CardHeader>
          <CardBody>
            {pie.length === 0 ? <p className="text-ink-dim">No claims yet.</p> : (
              <div className="space-y-5">
                <div className="flex items-baseline gap-3">
                  <span className="font-display text-4xl font-semibold leading-none">{s.total}</span>
                  <span className="text-sm uppercase tracking-wider text-ink-mut">total claims</span>
                </div>
                <ul className="space-y-4">
                  {pie.map((e) => {
                    const w = s.total ? Math.round((e.value / s.total) * 100) : 0;
                    return (
                      <li key={e.key}>
                        <div className="mb-1.5 flex items-center justify-between text-base">
                          <span className="flex items-center gap-2.5">
                            <span className="h-3 w-3 rounded-full" style={{ background: DEC_COLOR[e.key] }} />
                            {e.name}
                          </span>
                          <span className="tabular-nums text-ink-dim"><b className="text-ink">{e.value}</b> · {w}%</span>
                        </div>
                        <div className="h-3 w-full overflow-hidden rounded-full bg-line/50">
                          <div className="h-full rounded-full transition-all" style={{ width: `${w}%`, background: DEC_COLOR[e.key] }} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader><CardTitle>Claims per day</CardTitle><span className="ml-auto text-xs text-ink-mut">last 14 days</span></CardHeader>
          <CardBody>
            {perDay.length === 0 ? <p className="text-ink-dim">No data yet.</p> : (
              <div className="h-44">
                <ResponsiveContainer>
                  <AreaChart data={perDay} margin={{ left: 0, right: 0, top: 6, bottom: 0 }}>
                    <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#D8B567" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#D8B567" stopOpacity={0} />
                    </linearGradient></defs>
                    <XAxis dataKey="day" tick={{ fill: "#6b7787", fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                    <Tooltip content={<TipBox />} cursor={{ stroke: "#2e3744" }} />
                    <Area type="monotone" dataKey="count" stroke="#D8B567" strokeWidth={2} fill="url(#g)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6 max-[820px]:grid-cols-1">
        <Card>
          <CardHeader><CardTitle>Most common reasons</CardTitle></CardHeader>
          <CardBody>
            {(s.top_reasons || []).length === 0 ? <p className="text-ink-dim">No data yet.</p> : (
              <ul className="space-y-3">
                {s.top_reasons.map((r, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-line/60 text-xs font-semibold text-ink-dim">{i + 1}</span>
                    <span className="flex-1 text-base leading-snug">{r.reason}</span>
                    <span className="font-semibold tabular-nums text-ink-dim">{r.count}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader><CardTitle>By claim type</CardTitle><TrendingUp className="ml-auto h-4 w-4 text-ink-mut" /></CardHeader>
          <CardBody>
            {types.length === 0 ? <p className="text-ink-dim">No data yet.</p> : (
              <ul className="space-y-2.5">
                {types.map((t) => {
                  const max = types[0]?.count || 1;
                  const pct = Math.max(3, Math.round((t.count / max) * 100));
                  return (
                    <li key={t.name}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="truncate pr-2 capitalize text-ink-dim">{t.name.replace(/_/g, " ")}</span>
                        <span className="font-semibold tabular-nums">{t.count}</span>
                      </div>
                      <div className="mt-1 h-2 w-full overflow-hidden rounded-full" style={{ background: "#161C25" }}>
                        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: "#D8B567" }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
