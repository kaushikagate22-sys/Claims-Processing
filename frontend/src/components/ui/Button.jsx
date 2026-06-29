import { cva } from "class-variance-authority";
import { cn } from "../../lib/cn.js";

const styles = cva(
  "inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold/60 disabled:opacity-50 disabled:pointer-events-none select-none whitespace-nowrap",
  {
    variants: {
      variant: {
        gold: "bg-gradient-to-b from-gold-2 to-gold text-ground shadow-[0_1px_0_rgba(255,255,255,0.25)_inset,0_6px_18px_-6px_rgba(216,181,103,0.6)] hover:brightness-105 active:translate-y-px",
        solid: "bg-raised text-ink border border-line-2 hover:border-gold/40 hover:bg-line/40",
        ghost: "text-ink-dim hover:text-ink hover:bg-line/40",
        outline: "border border-line-2 text-ink hover:border-gold/40",
        danger: "bg-reject/15 text-reject border border-reject/30 hover:bg-reject/25",
      },
      size: { sm: "h-8 px-3 text-sm", md: "h-10 px-4 text-base", lg: "h-12 px-6 text-base", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "solid", size: "md" },
  }
);

export function Button({ className, variant, size, ...props }) {
  return <button className={cn(styles({ variant, size }), className)} {...props} />;
}
