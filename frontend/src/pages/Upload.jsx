import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { navigate } from "../App.jsx";
import { money, DECISION_TONE, DECISION_LABEL } from "../lib/format.js";
import { Card, CardHeader, CardTitle, CardBody } from "../components/ui/Card.jsx";
import { Button } from "../components/ui/Button.jsx";
import { Badge } from "../components/ui/Badge.jsx";
import { Textarea } from "../components/ui/Field.jsx";
import PipelineConsole from "../components/PipelineConsole.jsx";
import { UploadCloud, FileText, Image as ImageIcon } from "lucide-react";

const SAMPLE = `WARRANTY CLAIM FORM
Claimant Name: Sunrise Dealers
Claim Type: warranty
Machine Serial Number: MX-88231
Failure Code: HYD-204
Failed Part: hydraulic pump
Job Card Number: JC-2025-3001
Claim Amount: 48000
Description: hydraulic pump failure under warranty, replaced and tested.`;

function Recent() {
  const [claims, setClaims] = useState([]);
  useEffect(() => { api.listClaims().then((c) => setClaims(c.slice(0, 8))).catch(() => {}); }, []);
  return (
    <Card>
      <CardHeader><CardTitle>Recent activity</CardTitle></CardHeader>
      <CardBody className="p-0">
        {claims.length === 0 ? <p className="px-6 py-5 text-ink-dim">No claims yet.</p> : (
          <ul className="divide-y divide-line">
            {claims.map((c) => (
              <li key={c.id}>
                <button onClick={() => navigate(`/claims/${c.id}`)} className="flex w-full items-center gap-3 px-6 py-3 text-left transition hover:bg-line/30">
                  <span className="font-mono text-sm text-ink-mut">#{c.id}</span>
                  <span className="flex-1 capitalize text-base">{(c.claim_type || "—").replace(/_/g, " ")}</span>
                  <Badge tone={DECISION_TONE[c.decision] || "muted"}>{DECISION_LABEL[c.decision] || "—"}</Badge>
                  <span className="w-24 text-right font-mono text-sm tabular-nums">{money(c.approved_amount)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

export default function Upload() {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [run, setRun] = useState(null);
  const inputRef = useRef(null);
  const photoRef = useRef(null);

  if (run) return <PipelineConsole start={run.start} onReset={() => setRun(null)} />;

  return (
    <div className="grid grid-cols-[1.3fr_1fr] gap-6 max-[1000px]:grid-cols-1">
      <div className="space-y-6">
        <Card>
          <CardHeader><CardTitle>Upload a claim file</CardTitle></CardHeader>
          <CardBody>
            <p className="mt-0 mb-3 text-sm text-ink-dim">Accepts .txt, .md, .pdf or .docx — the engine reads any layout.</p>
            <div
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]); }}
              className={"flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition " +
                (dragOver ? "border-gold bg-gold/5" : file ? "border-approve/40 bg-approve/5" : "border-line-2 hover:border-gold/40 hover:bg-line/20")}>
              <input ref={inputRef} type="file" accept=".txt,.md,.pdf,.docx" hidden onChange={(e) => setFile(e.target.files?.[0] || null)} />
              {file ? (
                <><FileText className="h-7 w-7 text-approve" /><strong className="text-base">{file.name}</strong><span className="font-mono text-xs text-ink-mut">{(file.size / 1024).toFixed(1)} KB</span></>
              ) : (
                <><UploadCloud className="h-7 w-7 text-ink-mut" /><span className="text-base text-ink-dim">Drop a file here, or click to browse</span></>
              )}
            </div>
            <div className="mt-4 rounded-xl border border-line bg-ground/40 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 text-base font-medium"><ImageIcon className="h-4 w-4 text-gold" />Photos (optional)</div>
                  <p className="mt-0.5 text-sm text-ink-dim">Attach claim photos — the engine checks them against the description.</p>
                </div>
                <Button variant="solid" size="sm" onClick={() => photoRef.current?.click()}>Add photos</Button>
                <input ref={photoRef} type="file" accept="image/*" multiple hidden
                  onChange={(e) => setPhotos((prev) => [...prev, ...Array.from(e.target.files || [])])} />
              </div>
              {photos.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {photos.map((p, i) => (
                    <span key={i} className="flex items-center gap-2 rounded-lg border border-line-2 bg-raised px-2.5 py-1.5 text-sm">
                      <ImageIcon className="h-3.5 w-3.5 text-ink-mut" />{p.name}
                      <button onClick={() => setPhotos((prev) => prev.filter((_, j) => j !== i))} className="text-ink-mut hover:text-reject">×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>
            <Button variant="gold" className="mt-4" disabled={!file} onClick={() => setRun({ start: () => api.streamFile(file, photos) })}>Run pipeline</Button>
          </CardBody>
        </Card>

        <Card>
          <CardHeader><CardTitle>Or paste claim text</CardTitle>
            <button className="ml-auto text-sm font-medium text-gold hover:text-gold-2" onClick={() => setText(SAMPLE)}>Insert example</button>
          </CardHeader>
          <CardBody>
            <Textarea rows={9} placeholder="Paste the claim details here…" value={text} onChange={(e) => setText(e.target.value)} />
            <Button variant="gold" className="mt-4" disabled={!text.trim()} onClick={() => setRun({ start: () => api.streamText(text) })}>Run pipeline</Button>
          </CardBody>
        </Card>
      </div>
      <Recent />
    </div>
  );
}
