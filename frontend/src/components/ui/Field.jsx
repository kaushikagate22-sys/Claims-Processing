import { cn } from "../../lib/cn.js";
export function Input({ className, ...props }) {
  return <input className={cn("h-10 w-full rounded-lg border border-line-2 bg-raised px-3 text-base text-ink placeholder:text-ink-mut focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:border-gold/40 transition", className)} {...props} />;
}
export function Textarea({ className, ...props }) {
  return <textarea className={cn("w-full rounded-lg border border-line-2 bg-raised px-3 py-2.5 text-base leading-relaxed text-ink placeholder:text-ink-mut focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/50 focus-visible:border-gold/40 transition font-mono", className)} {...props} />;
}
export function Label({ className, ...props }) {
  return <label className={cn("text-xs font-semibold uppercase tracking-wider text-ink-mut", className)} {...props} />;
}
