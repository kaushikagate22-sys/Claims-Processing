import { useEffect, useState } from "react";
import { api } from "../api.js";
import { navigate } from "../App.jsx";
import { money, pct, dateTime, ruleLabel, severityLabel, severityRole, severityTone, DECISION_TONE, DECISION_LABEL } from "../lib/format.js";
import { Card, CardHeader, CardTitle, CardBody } from "../components/ui/Card.jsx";
import { Button } from "../components/ui/Button.jsx";
import { Badge } from "../components/ui/Badge.jsx";
import { Skeleton } from "../components/ui/Skeleton.jsx";
import { Check, X, ArrowLeft, ListChecks, FileText, Bell, Camera } from "lucide-react";

const TONE_RING = { approve: "from-approve/20", hold: "from-hold/20", escalate: "from-escalate/20", reject: "from-reject/20" };
const TONE_TEXT = { approve: "text-approve", hold: "text-hold", escalate: "text-escalate", reject: "text-reject" };
const prettyKey = (k) => k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

function RuleRow({ r }) {
  return (
    <li className="flex items-start gap-3 py-2.5">
      <span className={"mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md " + (r.passed ? "bg-approve/15 text-approve" : "bg-reject/15 text-reject")}>
        {r.passed ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
      </span>
      <div className="flex-1">
        <div className="text-base leading-tight">{ruleLabel(r.id)}</div>
        {!r.passed && r.message && <div className="mt-0.5 text-sm text-reject/90">{r.message}</div>}
      </div>
      {r.passed
        ? <Badge tone="muted">{severityRole(r.severity)}</Badge>
        : <Badge tone={severityTone(r.severity)}>{severityLabel(r.severity)}</Badge>}
    </li>
  );
}

function Field({ label, value, mono }) {
  return (
    <div className="border-b border-line py-2.5 last:border-0">
      <div className="text-xs font-semibold uppercase tracking-wider text-ink-mut">{label}</div>
      <div className={"mt-0.5 text-base " + (mono ? "font-mono" : "")}>{value ?? "—"}</div>
    </div>
  );
}

export default function Decision({ id }) {
  const [claim, setClaim] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { setClaim(null); api.getClaim(id).then(setClaim).catch((e) => setError(e.message)); }, [id]);

  if (error) return <div className="rounded-xl border border-reject/30 bg-reject/10 p-4 text-reject">{error}</div>;
  if (!claim) return <div className="space-y-5"><Skeleton className="h-40" /><div className="grid grid-cols-2 gap-6"><Skeleton className="h-60" /><Skeleton className="h-60" /></div></div>;

  const adj = claim.adjudication || {};
  const ext = claim.extracted || {};
  const val = claim.validation || {};
  const vis = claim.visual_validation || {};
  const tone = DECISION_TONE[claim.decision] || "hold";
  const outcomes = adj.rule_outcomes || [];
  const failed = outcomes.filter((r) => !r.passed);
  const passed = outcomes.filter((r) => r.passed);
  const extra = ext.extra || {};

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button onClick={() => navigate("/claims")} className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-dim hover:text-ink"><ArrowLeft className="h-4 w-4" />All claims</button>
        <span className="font-mono text-xs text-ink-mut">{claim.run_id} · {dateTime(claim.created_at)}</span>
      </div>

      {/* verdict */}
      <div className={"relative overflow-hidden rounded-2xl border border-line bg-gradient-to-br to-transparent p-7 " + (TONE_RING[tone] || "")}>
        <span className="text-xs font-semibold uppercase tracking-wider text-ink-mut">Claim #{claim.id} · {(claim.claim_type || "—").replace(/_/g, " ")}</span>
        <h1 className={"mt-1 font-display text-6xl font-semibold leading-none tracking-tight " + (TONE_TEXT[tone] || "")}>{DECISION_LABEL[claim.decision] || claim.decision}</h1>
        <div className="mt-5 flex flex-wrap gap-8">
          <div><div className="text-xs uppercase tracking-wider text-ink-mut">Payout</div><div className="mt-0.5 font-display text-2xl font-semibold">{money(adj.approved_amount)}</div></div>
          <div><div className="text-xs uppercase tracking-wider text-ink-mut">Claimed</div><div className="mt-0.5 font-display text-2xl font-semibold">{money(ext.claim_amount)}</div></div>
          <div><div className="text-xs uppercase tracking-wider text-ink-mut">Confidence</div><div className="mt-0.5 font-display text-2xl font-semibold">{pct(adj.confidence)}</div></div>
          <div className="flex items-end"><Button variant="solid" size="sm" onClick={() => navigate(`/claims/${claim.id}/diagnostics`)}>Diagnostics</Button></div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6 max-[820px]:grid-cols-1">
        <Card><CardHeader><CardTitle>Why</CardTitle></CardHeader>
          <CardBody><ul className="list-disc space-y-1.5 pl-5 text-base leading-relaxed marker:text-gold">{(adj.reasons || []).map((r, i) => <li key={i}>{r}</li>)}</ul></CardBody></Card>
        <Card><CardHeader><CardTitle>Next steps</CardTitle></CardHeader>
          <CardBody><ul className="list-disc space-y-1.5 pl-5 text-base leading-relaxed marker:text-gold">{(adj.next_steps || []).map((r, i) => <li key={i}>{r}</li>)}</ul></CardBody></Card>
      </div>

      {/* audit summary + draft notification email */}
      {claim.summary && (
        <Card>
          <CardHeader><FileText className="h-5 w-5 text-gold" /><CardTitle>Audit summary</CardTitle></CardHeader>
          <CardBody><p className="text-base leading-relaxed text-ink">{claim.summary}</p></CardBody>
        </Card>
      )}
      {claim.notification && (
        <Card>
          <CardHeader>
            <Bell className="h-5 w-5 text-gold" /><CardTitle>Notification email</CardTitle>
            <Badge className="ml-auto" tone={["queued", "sent"].includes(claim.notification.status) ? "approve" : "reject"}>
              {claim.notification.status === "sent" ? "Sent" : claim.notification.status === "queued" ? "Draft · queued" : claim.notification.status || "—"}
            </Badge>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-base">
              <span className="text-ink-mut">To</span><span>{claim.notification.recipient || claim.notification.to}</span>
              <span className="text-ink-mut">Channel</span><span className="capitalize">{claim.notification.channel}</span>
              <span className="text-ink-mut">Subject</span><span className="font-medium">{claim.notification.subject}</span>
            </div>
            {claim.notification.body && (
              <pre className="mt-4 whitespace-pre-wrap rounded-xl border border-line bg-ground/60 p-4 font-sans text-base leading-relaxed text-ink">{claim.notification.body}</pre>
            )}
          </CardBody>
        </Card>
      )}

      {/* visual validation */}
      {vis.photos_provided && (
        <Card>
          <CardHeader>
            <Camera className="h-5 w-5 text-gold" /><CardTitle>Visual validation</CardTitle>
            <Badge className="ml-auto" tone={!vis.assessed ? "muted" : vis.consistent ? "approve" : "escalate"}>
              {!vis.assessed ? "Not assessed" : vis.consistent ? "Photos consistent" : "Mismatch"}
            </Badge>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-8">
              <div><div className="text-xs uppercase tracking-wider text-ink-mut">Photos</div><div className="mt-0.5 font-display text-xl font-semibold">{vis.photo_count}</div></div>
              <div><div className="text-xs uppercase tracking-wider text-ink-mut">Confidence</div><div className="mt-0.5 font-display text-xl font-semibold">{vis.assessed ? pct(vis.confidence) : "—"}</div></div>
              {vis.assessed && <div><div className="text-xs uppercase tracking-wider text-ink-mut">Criteria met</div><div className="mt-0.5 font-display text-xl font-semibold">{(vis.checks || []).filter((c) => c.pass).length}/{(vis.checks || []).length}</div></div>}
            </div>
            {vis.findings && <p className="mt-4 text-base leading-relaxed text-ink-dim">{vis.findings}</p>}
            {Array.isArray(vis.checks) && vis.checks.length > 0 && (
              <ul className="mt-4 divide-y divide-line">
                {vis.checks.map((c, i) => (
                  <li key={i} className="flex items-start gap-3 py-2.5">
                    <span className={"mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md " + (c.pass ? "bg-approve/15 text-approve" : "bg-escalate/15 text-escalate")}>
                      {c.pass ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                    </span>
                    <div className="flex-1">
                      <div className="text-base leading-tight">{c.criterion}</div>
                      {c.observation && <div className="mt-0.5 text-sm text-ink-mut">{c.observation}</div>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      )}

      {/* rule scorecard */}
      <Card>
        <CardHeader><ListChecks className="h-5 w-5 text-gold" /><CardTitle>Rule checks</CardTitle>
          <span className="ml-auto text-sm"><span className="text-approve">{passed.length} passed</span><span className="mx-2 text-line-2">·</span><span className={failed.length ? "text-reject" : "text-ink-mut"}>{failed.length} failed</span></span>
        </CardHeader>
        <CardBody className="py-2">
          <ul className="divide-y divide-line">
            {failed.map((r) => <RuleRow key={r.id} r={r} />)}
            {passed.map((r) => <RuleRow key={r.id} r={r} />)}
          </ul>
        </CardBody>
      </Card>

      {/* extracted + duplicate */}
      <div className="grid grid-cols-2 gap-6 max-[820px]:grid-cols-1">
        <Card><CardHeader><CardTitle>Extracted details</CardTitle></CardHeader>
          <CardBody className="py-2">
            <Field label="Claimant" value={ext.claimant_name} />
            <Field label="Reference" value={ext.claim_reference} mono />
            <Field label="Claim type" value={(claim.claim_type || "—").replace(/_/g, " ")} />
            <Field label="Claim amount" value={money(ext.claim_amount)} mono />
            <Field label="Completeness" value={pct(claim.completeness)} mono />
            {Object.entries(extra).filter(([, v]) => v !== null && v !== "").map(([k, v]) => <Field key={k} label={prettyKey(k)} value={String(v)} mono />)}
            {ext.description && <div className="pt-3 text-base leading-relaxed text-ink-dim">{ext.description}</div>}
          </CardBody>
        </Card>
        {val.performed ? (
          <Card><CardHeader><CardTitle>Record validation</CardTitle><span className="ml-auto text-sm text-ink-mut">system of record</span></CardHeader>
            <CardBody className="py-2">
              {(val.record_checks && val.record_checks.length > 0) ? (
                <ul className="divide-y divide-line">
                  {val.record_checks.map((c) => (
                    <li key={c.key} className="flex items-start gap-3 py-2.5">
                      <span className={"mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md " + (c.ok ? "bg-approve/15 text-approve" : "bg-escalate/15 text-escalate")}>
                        {c.ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                      </span>
                      <div className="flex-1">
                        <div className="text-base leading-tight">{c.label}</div>
                        {c.detail && <div className="mt-0.5 font-mono text-sm text-ink-mut">{c.detail}</div>}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <>
                  <Field label="Duplicate key" value={prettyKey(val.duplicate_key || "—")} mono />
                  <Field label="Value checked" value={val.duplicate_value || "—"} mono />
                  <Field label="Duplicate found" value={val.is_duplicate ? "Yes" : "No"} />
                </>
              )}
            </CardBody>
          </Card>
        ) : <div />}
      </div>
    </div>
  );
}
