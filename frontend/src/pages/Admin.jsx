import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { money } from "../lib/format.js";
import { Card, CardHeader, CardTitle, CardBody } from "../components/ui/Card.jsx";
import { Button } from "../components/ui/Button.jsx";
import { Badge } from "../components/ui/Badge.jsx";
import { Input, Textarea, Label } from "../components/ui/Field.jsx";
import { Select } from "../components/ui/Select.jsx";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/Tabs.jsx";
import { Trash2, Plus, ChevronDown, ChevronRight, Upload as UploadIcon, Download } from "lucide-react";

function Alert({ kind, children }) {
  const c = kind === "ok" ? "border-approve/30 bg-approve/10 text-approve" : kind === "err" ? "border-reject/30 bg-reject/10 text-reject" : "border-gold/30 bg-gold/10 text-gold-2";
  return <div className={"rounded-xl border p-3.5 text-sm " + c}>{children}</div>;
}

function FileButton({ label, accept, onPick, busy }) {
  const ref = useRef(null);
  return (<>
    <input ref={ref} type="file" accept={accept} hidden onChange={(e) => e.target.files?.[0] && onPick(e.target.files[0])} />
    <Button variant="solid" size="sm" disabled={busy} onClick={() => ref.current?.click()}><UploadIcon className="h-4 w-4" />{busy ? "Uploading…" : label}</Button>
  </>);
}

/* ----------------------------- Policy ----------------------------- */
function PolicyTab() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const fileRef = useRef(null);
  useEffect(() => { api.getPolicy().then((p) => setText(p.text)).catch((e) => setMsg({ kind: "err", text: e.message })); }, []);

  async function save() {
    setBusy(true); setMsg(null);
    try { const r = await api.savePolicy(text); setMsg({ kind: "ok", text: `Saved (compiled via ${r.mode}).` }); }
    catch (e) { setMsg({ kind: "err", text: e.message }); } finally { setBusy(false); }
  }
  async function uploadFile(file) {
    setBusy(true); setMsg(null);
    try { await api.uploadPolicyFile(file); const p = await api.getPolicy(); setText(p.text); setMsg({ kind: "ok", text: "Policy document replaced." }); }
    catch (e) { setMsg({ kind: "err", text: e.message }); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <Alert kind="info">This document is reference for reviewers and supplies context on decisions. It does <b>not</b> drive the validation rules — edit those in the <b>Claim types</b> tab.</Alert>
      <Card>
        <CardHeader><CardTitle>Policy document</CardTitle>
          <span className="ml-auto flex gap-2">
            <input ref={fileRef} type="file" accept=".md,.txt" hidden onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])} />
            <Button variant="solid" size="sm" disabled={busy} onClick={() => fileRef.current?.click()}>Replace with file…</Button>
            <Button variant="gold" size="sm" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save"}</Button>
          </span>
        </CardHeader>
        <CardBody>
          <Textarea rows={16} value={text} onChange={(e) => setText(e.target.value)} />
          {msg && <div className="mt-3"><Alert kind={msg.kind}>{msg.text}</Alert></div>}
        </CardBody>
      </Card>
    </div>
  );
}

/* --------------------------- Rule editor -------------------------- */
function TypeCard({ name, cfg, operators, severities }) {
  const [open, setOpen] = useState(false);
  const [checks, setChecks] = useState((cfg.checks || []).map((c) => ({ ...c })));
  const [fields, setFields] = useState(Object.entries(cfg.extraction_schema || {}).map(([k, v]) => ({ k, v })));
  const [visual, setVisual] = useState((cfg.visual_checks || []).slice());
  const [knobs, setKnobs] = useState({
    exclusion_keywords: (cfg.exclusion_keywords || []).join(", "),
    escalate_keywords: (cfg.escalate_keywords || []).join(", "),
    required_fields: (cfg.required_fields || []).join(", "),
    duplicate_key: cfg.duplicate_key || "",
    high_value_threshold: cfg.high_value_threshold ?? "",
    settlement_cap: cfg.settlement_cap ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const opts = cfg.field_options || [];
  const toList = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const setCheck = (i, k, v) => setChecks((cs) => cs.map((c, j) => (j === i ? { ...c, [k]: v } : c)));
  const addCheck = () => setChecks((cs) => [...cs, { id: "", field: opts[0] || "", op: "exists", value: "", severity: "hold", category: "completeness", message: "" }]);
  const delCheck = (i) => setChecks((cs) => cs.filter((_, j) => j !== i));
  const setField = (i, k, v) => setFields((fs) => fs.map((f, j) => (j === i ? { ...f, [k]: v } : f)));

  async function saveRules() {
    setBusy(true); setMsg(null);
    const config = {
      exclusion_keywords: toList(knobs.exclusion_keywords), escalate_keywords: toList(knobs.escalate_keywords),
      required_fields: toList(knobs.required_fields), duplicate_key: knobs.duplicate_key || null,
      high_value_threshold: knobs.high_value_threshold === "" ? null : Number(knobs.high_value_threshold),
      settlement_cap: knobs.settlement_cap === "" ? null : Number(knobs.settlement_cap),
    };
    try { await api.saveTypeRules(name, checks.filter((c) => c.id && c.field && c.op), config); setMsg({ kind: "ok", text: "Rules saved. Live decisions now use these." }); }
    catch (e) { setMsg({ kind: "err", text: e.message }); } finally { setBusy(false); }
  }
  async function saveFields() {
    setBusy(true); setMsg(null);
    const f = {}; for (const r of fields) if (r.k.trim()) f[r.k.trim()] = r.v.trim();
    try { await api.saveTypeFields(name, f); setMsg({ kind: "ok", text: "Extraction fields saved." }); }
    catch (e) { setMsg({ kind: "err", text: e.message }); } finally { setBusy(false); }
  }
  async function saveVisual() {
    setBusy(true); setMsg(null);
    try { await api.saveTypeVisual(name, visual.map((s) => s.trim()).filter(Boolean)); setMsg({ kind: "ok", text: "Visual checks saved. The visual agent now reports against these." }); }
    catch (e) { setMsg({ kind: "err", text: e.message }); } finally { setBusy(false); }
  }

  return (
    <Card>
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 px-6 py-4 text-left">
        {open ? <ChevronDown className="h-5 w-5 text-gold" /> : <ChevronRight className="h-5 w-5 text-ink-mut" />}
        <CardTitle className="capitalize">{cfg.label || name.replace(/_/g, " ")}</CardTitle>
        <Badge tone="muted" className="ml-1">{(cfg.checks || []).length} rules</Badge>
        <span className="ml-auto text-sm text-ink-mut">{open ? "Collapse" : "Edit"}</span>
      </button>

      {open && (
        <CardBody className="border-t border-line space-y-6">
          <div>
            <Label>Validation rules</Label>
            <p className="mb-3 mt-1 text-sm text-ink-dim">Each runs against the claim. Severity sets the outcome — <span className="text-reject">reject</span>, <span className="text-hold">hold</span>, <span className="text-escalate">escalate</span>.</p>
            <div className="overflow-x-auto rounded-xl border border-line">
              <table className="w-full text-sm">
                <thead className="border-b border-line bg-panel text-left text-xs uppercase tracking-wider text-ink-mut">
                  <tr><th className="px-3 py-2 font-semibold">Rule id</th><th className="px-3 py-2 font-semibold">Field</th><th className="px-3 py-2 font-semibold">Operator</th><th className="px-3 py-2 font-semibold">Value</th><th className="px-3 py-2 font-semibold">Severity</th><th className="px-3 py-2 font-semibold">Message</th><th /></tr>
                </thead>
                <tbody>
                  {checks.map((c, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      <td className="px-2 py-1.5"><Input className="h-9 font-mono text-sm" value={c.id} onChange={(e) => setCheck(i, "id", e.target.value)} /></td>
                      <td className="px-2 py-1.5"><Select className="w-full" value={c.field} onValueChange={(v) => setCheck(i, "field", v)} options={opts.includes(c.field) ? opts : [c.field, ...opts]} /></td>
                      <td className="px-2 py-1.5"><Select className="w-full" value={c.op} onValueChange={(v) => setCheck(i, "op", v)} options={operators} /></td>
                      <td className="px-2 py-1.5"><Input className="h-9 w-24 text-sm" value={c.value ?? ""} placeholder="—" onChange={(e) => setCheck(i, "value", e.target.value)} /></td>
                      <td className="px-2 py-1.5"><Select className="w-full" value={c.severity} onValueChange={(v) => setCheck(i, "severity", v)} options={severities} /></td>
                      <td className="px-2 py-1.5"><Input className="h-9 text-sm" value={c.message || ""} onChange={(e) => setCheck(i, "message", e.target.value)} /></td>
                      <td className="px-2 py-1.5"><button onClick={() => delCheck(i)} className="text-ink-mut hover:text-reject"><Trash2 className="h-4 w-4" /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex gap-2">
              <Button variant="solid" size="sm" onClick={addCheck}><Plus className="h-4 w-4" />Add rule</Button>
              <Button variant="gold" size="sm" disabled={busy} onClick={saveRules}>{busy ? "Saving…" : "Save rules"}</Button>
            </div>
          </div>

          <div>
            <Label>Configuration</Label>
            <div className="mt-2 grid grid-cols-2 gap-4 max-[680px]:grid-cols-1">
              <div><span className="text-xs text-ink-mut">Exclusion keywords (→ reject)</span><Input className="mt-1" value={knobs.exclusion_keywords} onChange={(e) => setKnobs({ ...knobs, exclusion_keywords: e.target.value })} /></div>
              <div><span className="text-xs text-ink-mut">Escalation keywords (→ escalate)</span><Input className="mt-1" value={knobs.escalate_keywords} onChange={(e) => setKnobs({ ...knobs, escalate_keywords: e.target.value })} /></div>
              <div><span className="text-xs text-ink-mut">Required fields (→ hold if missing)</span><Input className="mt-1" value={knobs.required_fields} onChange={(e) => setKnobs({ ...knobs, required_fields: e.target.value })} /></div>
              <div><span className="text-xs text-ink-mut">Duplicate key</span><div className="mt-1"><Select className="w-full" value={knobs.duplicate_key} onValueChange={(v) => setKnobs({ ...knobs, duplicate_key: v })} options={["", ...opts]} placeholder="(none)" /></div></div>
              <div><span className="text-xs text-ink-mut">High-value threshold (→ escalate)</span><Input className="mt-1" type="number" value={knobs.high_value_threshold} onChange={(e) => setKnobs({ ...knobs, high_value_threshold: e.target.value })} /></div>
              <div><span className="text-xs text-ink-mut">Settlement cap (payout limit)</span><Input className="mt-1" type="number" value={knobs.settlement_cap} onChange={(e) => setKnobs({ ...knobs, settlement_cap: e.target.value })} /></div>
            </div>
          </div>

          <div>
            <Label>Extraction fields</Label>
            <p className="mb-2 mt-1 text-sm text-ink-dim">What the engine pulls from each claim (name → what to pull).</p>
            <div className="space-y-2">
              {fields.map((r, i) => (
                <div key={i} className="flex gap-2">
                  <Input className="w-52 font-mono text-sm" value={r.k} placeholder="field_name" onChange={(e) => setField(i, "k", e.target.value)} />
                  <Input className="flex-1 text-sm" value={r.v} placeholder="what to extract" onChange={(e) => setField(i, "v", e.target.value)} />
                  <button onClick={() => setFields((fs) => fs.filter((_, j) => j !== i))} className="text-ink-mut hover:text-reject px-2"><Trash2 className="h-4 w-4" /></button>
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <Button variant="solid" size="sm" onClick={() => setFields((fs) => [...fs, { k: "", v: "" }])}><Plus className="h-4 w-4" />Add field</Button>
              <Button variant="gold" size="sm" disabled={busy} onClick={saveFields}>{busy ? "Saving…" : "Save fields"}</Button>
            </div>
          </div>

          <div>
            <Label>Visual checks (photo validation)</Label>
            <p className="mb-2 mt-1 text-sm text-ink-dim">What the visual agent inspects in the claim's photos. It reports an observation for each. A failed check escalates the claim.</p>
            <div className="space-y-2">
              {visual.map((c, i) => (
                <div key={i} className="flex gap-2">
                  <span className="mt-2.5 w-5 shrink-0 text-right font-mono text-xs text-ink-mut">{i + 1}</span>
                  <Input className="flex-1 text-sm" value={c} placeholder="e.g. The photo shows the failed part described in the claim" onChange={(e) => setVisual((vs) => vs.map((x, j) => (j === i ? e.target.value : x)))} />
                  <button onClick={() => setVisual((vs) => vs.filter((_, j) => j !== i))} className="text-ink-mut hover:text-reject px-2"><Trash2 className="h-4 w-4" /></button>
                </div>
              ))}
              {visual.length === 0 && <p className="text-sm text-ink-mut">No visual checks. Add up to 6 — these are the criteria the photo is judged against.</p>}
            </div>
            <div className="mt-3 flex gap-2">
              <Button variant="solid" size="sm" disabled={visual.length >= 6} onClick={() => setVisual((vs) => [...vs, ""])}><Plus className="h-4 w-4" />Add check</Button>
              <Button variant="gold" size="sm" disabled={busy} onClick={saveVisual}>{busy ? "Saving…" : "Save visual checks"}</Button>
            </div>
          </div>

          {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
        </CardBody>
      )}
    </Card>
  );
}

function TypesTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.getTypes().then(setData).catch((e) => setErr(e.message)); }, []);
  if (err) return <Alert kind="err">{err}</Alert>;
  if (!data) return <Card><CardBody className="text-ink-dim">Loading types…</CardBody></Card>;
  return (
    <div className="space-y-4">
      <Alert kind="ok">These rules are the source of truth for live decisions. Click <b>Edit</b> on a type to change its rules, exclusions, thresholds and fields. Changes apply immediately.</Alert>
      {Object.entries(data.types).map(([name, cfg]) => (
        <TypeCard key={name} name={name} cfg={cfg} operators={data.operators} severities={data.severities} />
      ))}
    </div>
  );
}

/* ----------------------------- Records ---------------------------- */
function RecordsTab() {
  const [data, setData] = useState({ policies: [], history: [] });
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState(null);
  const load = () => api.getRecords().then(setData);
  useEffect(() => { load().catch((e) => setMsg({ kind: "err", text: e.message })); }, []);
  async function upload(kind, file) {
    setBusy(kind); setMsg(null);
    try { const r = kind === "policies" ? await api.uploadPolicies(file) : await api.uploadHistory(file); await load(); setMsg({ kind: "ok", text: `Loaded ${r.count} ${kind} row(s).` }); }
    catch (e) { setMsg({ kind: "err", text: e.message }); } finally { setBusy(""); }
  }
  return (
    <div className="space-y-5">
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      <Card className="overflow-hidden">
        <CardHeader><CardTitle>Claims history</CardTitle><Badge tone="muted">{data.history.length}</Badge>
          <span className="ml-auto"><FileButton label="Upload CSV/XLSX" accept=".csv,.xlsx" busy={busy === "history"} onPick={(f) => upload("history", f)} /></span></CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-base">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-mut"><tr><th className="px-5 py-2.5">Reference</th><th className="px-5 py-2.5">Type</th><th className="px-5 py-2.5">Status</th><th className="px-5 py-2.5 text-right">Paid</th></tr></thead>
            <tbody>{data.history.map((h, i) => (<tr key={i} className="border-b border-line last:border-0"><td className="px-5 py-2.5 font-mono">{h.reference || h.claim_ref || "—"}</td><td className="px-5 py-2.5 capitalize text-ink-dim">{(h.claim_type || "—").replace(/_/g, " ")}</td><td className="px-5 py-2.5">{h.status || "—"}</td><td className="px-5 py-2.5 text-right font-mono">{money(h.paid_amount)}</td></tr>))}</tbody>
          </table>
          {data.history.length === 0 && <p className="px-5 py-6 text-ink-dim">No history rows.</p>}
        </div>
      </Card>
    </div>
  );
}

/* ----------------------------- Masters ---------------------------- */
function csvCell(v) {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function MasterCard({ m, busy, onUpload, onDownload }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-wrap gap-y-2">
        <CardTitle className="capitalize">{m.label}</CardTitle>
        <Badge tone="muted">{m.count} rows</Badge>
        <span className="ml-auto flex gap-2">
          <Button variant="solid" size="sm" onClick={() => onDownload(m)}><Download className="h-4 w-4" />Download CSV</Button>
          <FileButton label="Replace CSV/XLSX" accept=".csv,.xlsx" busy={busy === m.kind} onPick={(f) => onUpload(m.kind, f)} />
        </span>
      </CardHeader>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-left text-xs uppercase tracking-wider text-ink-mut">
            <tr>{m.columns.map((c) => <th key={c} className="px-4 py-2.5 font-semibold whitespace-nowrap">{c.replace(/_/g, " ")}</th>)}</tr>
          </thead>
          <tbody>
            {m.rows.slice(0, 8).map((r, i) => (
              <tr key={i} className="border-b border-line last:border-0">
                {m.columns.map((c) => <td key={c} className="px-4 py-2 font-mono whitespace-nowrap text-ink-dim">{r[c]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {m.rows.length > 8 && <p className="px-4 py-2.5 text-sm text-ink-mut">+ {m.rows.length - 8} more rows — download to see all.</p>}
        {m.rows.length === 0 && <p className="px-4 py-6 text-ink-dim">No rows. Upload a CSV to populate this master.</p>}
      </div>
    </Card>
  );
}

function MastersTab() {
  const [masters, setMasters] = useState(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState(null);
  const load = () => api.getMasters().then((d) => setMasters(d.masters));
  useEffect(() => { load().catch((e) => setMsg({ kind: "err", text: e.message })); }, []);

  async function upload(kind, file) {
    setBusy(kind); setMsg(null);
    try { const r = await api.uploadMaster(kind, file); await load(); setMsg({ kind: "ok", text: `${kind} master updated — ${r.rows} rows. Used by validation immediately.` }); }
    catch (e) { setMsg({ kind: "err", text: e.message }); } finally { setBusy(""); }
  }
  function download(m) {
    const head = m.columns.join(",");
    const body = m.rows.map((r) => m.columns.map((c) => csvCell(r[c])).join(",")).join("\n");
    const blob = new Blob([head + "\n" + body], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${m.kind}_master.csv`; a.click();
    URL.revokeObjectURL(a.href);
  }

  if (!masters) return <Card><CardBody className="text-ink-dim">Loading masters…</CardBody></Card>;
  return (
    <div className="space-y-4">
      <Alert kind="ok">These are the system-of-record files the validation agent checks claims against. Download one, edit it in Excel, and upload it back — changes apply to the next claim immediately. Keep the column headers unchanged.</Alert>
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
      {masters.map((m) => <MasterCard key={m.kind} m={m} busy={busy} onUpload={upload} onDownload={download} />)}
    </div>
  );
}

export default function Admin() {
  return (
    <Tabs defaultValue="types">
      <TabsList className="mb-5">
        <TabsTrigger value="types">Claim types</TabsTrigger>
        <TabsTrigger value="masters">Masters</TabsTrigger>
        <TabsTrigger value="policy">Policy &amp; reference</TabsTrigger>
        <TabsTrigger value="records">Records</TabsTrigger>
      </TabsList>
      <TabsContent value="types"><TypesTab /></TabsContent>
      <TabsContent value="masters"><MastersTab /></TabsContent>
      <TabsContent value="policy"><PolicyTab /></TabsContent>
      <TabsContent value="records"><RecordsTab /></TabsContent>
    </Tabs>
  );
}
