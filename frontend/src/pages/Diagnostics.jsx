import { useEffect, useState } from "react";
import { api } from "../api.js";
import { ruleLabel, ruleCategory, severityLabel, severityRole, severityTone, DECISION_LABEL } from "../lib/format.js";
import { Card, CardHeader, CardTitle, CardBody } from "../components/ui/Card.jsx";
import { Badge } from "../components/ui/Badge.jsx";
import { Skeleton } from "../components/ui/Skeleton.jsx";
import { Check, X, ArrowLeft } from "lucide-react";

function CheckRow({ r }) {
  return (
    <li className="flex items-start gap-3 py-2.5">
      <span className={"mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md " + (r.passed ? "bg-approve/15 text-approve" : "bg-reject/15 text-reject")}>
        {r.passed ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
      </span>
      <div className="flex-1">
        <div className="text-base leading-tight">{ruleLabel(r.id)}</div>
        {!r.passed && r.message && <div className="mt-0.5 text-sm text-reject/90">{r.message}</div>}
      </div>
      <Badge tone="muted">{ruleCategory(r.id)}</Badge>
      {r.passed
        ? <Badge tone="muted">{severityRole(r.severity)}</Badge>
        : <Badge tone={severityTone(r.severity)}>{severityLabel(r.severity)}</Badge>}
    </li>
  );
}

export default function Diagnostics({ id }) {
  const [claim, setClaim] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { setClaim(null); api.getClaim(id).then(setClaim).catch((e) => setError(e.message)); }, [id]);

  if (error) return <div className="rounded-xl border border-reject/30 bg-reject/10 p-4 text-reject">{error}</div>;
  if (!claim) return <div className="space-y-4"><Skeleton className="h-10 w-64" /><Skeleton className="h-72" /></div>;

  const outcomes = claim.adjudication?.rule_outcomes || [];
  const passed = outcomes.filter((r) => r.passed);
  const failed = outcomes.filter((r) => !r.passed);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <a href={`#/claims/${claim.id}`} className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-dim hover:text-ink"><ArrowLeft className="h-4 w-4" />Back to decision</a>
        <span className="text-sm"><span className="text-approve">{passed.length} passed</span><span className="mx-2 text-line-2">/</span><span className={failed.length ? "text-reject" : "text-ink-mut"}>{failed.length} failed</span></span>
      </div>
      <div>
        <span className="text-xs font-semibold uppercase tracking-wider text-gold">Diagnostics · Claim #{claim.id}</span>
        <p className="mt-1 text-ink-dim">Every rule evaluated against this claim. Decision: <strong className="text-ink">{DECISION_LABEL[claim.decision] || claim.decision}</strong>.</p>
      </div>

      {failed.length > 0 && (
        <Card><CardHeader><CardTitle className="text-reject">Failed checks</CardTitle></CardHeader>
          <CardBody className="py-2"><ul className="divide-y divide-line">{failed.map((r) => <CheckRow key={r.id} r={r} />)}</ul></CardBody></Card>
      )}
      <Card><CardHeader><CardTitle className="text-approve">Passed checks</CardTitle></CardHeader>
        <CardBody className="py-2">
          {passed.length === 0 ? <p className="text-ink-dim">No checks passed.</p>
            : <ul className="divide-y divide-line">{passed.map((r) => <CheckRow key={r.id} r={r} />)}</ul>}
        </CardBody></Card>
    </div>
  );
}
