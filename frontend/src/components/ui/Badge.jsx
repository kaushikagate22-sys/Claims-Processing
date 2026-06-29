import { cva } from "class-variance-authority";
import { cn } from "../../lib/cn.js";

const styles = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide uppercase border",
  {
    variants: {
      tone: {
        approve: "bg-approve/12 text-approve border-approve/30",
        hold: "bg-hold/12 text-hold border-hold/30",
        escalate: "bg-escalate/12 text-escalate border-escalate/30",
        reject: "bg-reject/12 text-reject border-reject/30",
        gold: "bg-gold/12 text-gold border-gold/30",
        muted: "bg-line/50 text-ink-dim border-line-2",
      },
    },
    defaultVariants: { tone: "muted" },
  }
);
export function Badge({ className, tone, ...props }) {
  return <span className={cn(styles({ tone }), className)} {...props} />;
}
