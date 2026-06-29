import { useEffect, useRef, useState } from "react";
import { navigate } from "../App.jsx";
import { DECISION_LABEL, DECISION_TONE, money } from "../lib/format.js";
import { Button } from "./ui/Button.jsx";
import { Badge } from "./ui/Badge.jsx";
import { Check, AlertTriangle, X, Loader2, ArrowRight } from "lucide-react";

const MIN_DWELL = 700;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const cap = (s) => (s || "").charAt(0).toUpperCase() + (s || "").slice(1);
const toneFor = (d) => ({ APPROVED: "green", HOLD: "amber", ESCALATE: "amber", REJECTED: "red" }[d] || "amber");

const NODE_STYLE = {
  idle: "border-line bg-panel text-ink-mut",
  running: "border-gold/60 bg-gold/5 text-ink shadow-[0_0_0_1px_rgba(216,181,103,0.3),0_0_30px_-8px_rgba(216,181,103,0.5)]",
  green: "border-approve/50 bg-approve/5 text-ink",
  amber: "border-hold/50 bg-hold/5 text-ink",
  red: "border-reject/50 bg-reject/5 text-ink",
};

export default function PipelineConsole({ start, onReset }) {
  const [agents, setAgents] = useState([]);
  const [nodes, setNodes] = useState({});
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const startTimes = useRef({});
  const logEnd = useRef(null);

  useEffect(() => { logEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [logs]);

  useEffect(() => {
    let cancelled = false;
    const pushLog = (kind, text) => setLogs((l) => [...l, { kind, text, t: new Date().toLocaleTimeString() }]);
    (async () => {
      try {
        for await (const ev of start()) {
          if (cancelled) return;
          if (ev.type === "run") {
            setAgents(ev.agents);
            setNodes(Object.fromEntries(ev.agents.map((_, i) => [i, { status: "idle" }])));
            pushLog("sys", `Run ${ev.run_id} started · ${ev.agents.length} agents`);
          } else if (ev.type === "agent_start") {
            startTimes.current[ev.index] = Date.now();
            setNodes((n) => ({ ...n, [ev.index]: { status: "running" } }));
            pushLog("run", `▶ ${cap(ev.agent)} — working…`);
          } else if (ev.type === "agent_done") {
            const elapsed = Date.now() - (startTimes.current[ev.index] || Date.now());
            if (elapsed < MIN_DWELL) await sleep(MIN_DWELL - elapsed);
            if (cancelled) return;
            setNodes((n) => ({ ...n, [ev.index]: { status: ev.tone, summary: ev.summary, ms: ev.duration_ms } }));
            pushLog(ev.tone, `✓ ${cap(ev.agent)} — ${ev.summary}`);
          } else if (ev.type === "done") {
            await sleep(350);
            if (cancelled) return;
            setResult(ev.claim);
            pushLog("sys", `Decision ready · ${DECISION_LABEL[ev.claim.decision] || ev.claim.decision}`);
          }
        }
      } catch (e) {
        if (!cancelled) { setError(e.message || "Stream failed. Is the API server running?"); pushLog("red", `✕ ${e.message}`); }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tone = result ? toneFor(result.decision) : null;

  return (
    <div className="space-y-6">
      <div>
        <span className="text-xs font-semibold uppercase tracking-[0.18em] text-gold">Live engine</span>
        <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight">Adjudication pipeline</h1>
        <p className="mt-1 text-ink-dim">Each agent runs in turn and hands off to the next.</p>
      </div>

      {/* pipeline nodes */}
      <div className="flex items-stretch gap-2 overflow-x-auto pb-2">
        {agents.map((a, i) => {
          const st = nodes[i]?.status || "idle";
          return (
            <div key={a.name} className="flex items-center gap-2">
              <div className={"w-44 shrink-0 rounded-2xl border p-4 transition-all duration-300 " + NODE_STYLE[st]}>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-ink-mut">{String(i + 1).padStart(2, "0")}</span>
                  {st === "idle" && <span className="h-2 w-2 rounded-full bg-ink-mut/40" />}
                  {st === "running" && <Loader2 className="h-4 w-4 animate-spin text-gold" />}
                  {st === "green" && <Check className="h-4 w-4 text-approve" />}
                  {st === "amber" && <AlertTriangle className="h-4 w-4 text-hold" />}
                  {st === "red" && <X className="h-4 w-4 text-reject" />}
                </div>
                <div className="mt-2 font-display text-lg font-medium">{cap(a.name)}</div>
                <div className="mt-0.5 text-xs leading-snug text-ink-dim">{a.info}</div>
                {nodes[i]?.ms != null && <div className="mt-2 font-mono text-xs text-ink-mut">{nodes[i].ms}ms</div>}
              </div>
              {i < agents.length - 1 && <ArrowRight className={"h-4 w-4 shrink-0 transition " + (nodes[i]?.status && nodes[i].status !== "idle" && nodes[i].status !== "running" ? "text-gold" : "text-line-2")} />}
            </div>
          );
        })}
      </div>

      {/* result */}
      {result && (
        <div className={"flex items-center justify-between gap-4 rounded-2xl border p-5 " +
          ({ green: "border-approve/40 bg-approve/8", amber: "border-hold/40 bg-hold/8", red: "border-reject/40 bg-reject/8" }[tone])}>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-ink-mut">Claim #{result.id} · {(result.claim_type || "").replace(/_/g, " ")}</div>
            <div className="mt-1 flex items-center gap-3">
              <span className="font-display text-2xl font-semibold">{DECISION_LABEL[result.decision] || result.decision}</span>
              <Badge tone={DECISION_TONE[result.decision] || "muted"}>{money(result.approved_amount)}</Badge>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="gold" onClick={() => navigate(`/claims/${result.id}`)}>View decision <ArrowRight className="h-4 w-4" /></Button>
            <Button variant="solid" onClick={onReset}>Run another</Button>
          </div>
        </div>
      )}
      {error && !result && (
        <div className="flex items-center justify-between rounded-2xl border border-reject/40 bg-reject/8 p-5">
          <span className="text-reject">{error}</span>
          <Button variant="solid" onClick={onReset}>Back</Button>
        </div>
      )}

      {/* log */}
      <div className="max-h-64 overflow-y-auto rounded-2xl border border-line bg-[#0a0d12] p-4 font-mono text-sm leading-relaxed">
        {logs.map((l, i) => {
          const c = { sys: "text-gold", run: "text-ink-dim", green: "text-approve", amber: "text-hold", red: "text-reject" }[l.kind] || "text-ink-dim";
          return (
            <div key={i} className="flex gap-3">
              <span className="text-ink-mut/60">{l.t}</span>
              <span className={c}>{l.text}</span>
            </div>
          );
        })}
        <div ref={logEnd} />
      </div>
    </div>
  );
}
