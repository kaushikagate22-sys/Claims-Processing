import { cn } from "../../lib/cn.js";

export function Card({ className, ...props }) {
  return <div className={cn("rounded-2xl border border-line bg-panel/80 backdrop-blur-sm shadow-[0_1px_0_rgba(255,255,255,0.03)_inset,0_20px_40px_-30px_rgba(0,0,0,0.8)]", className)} {...props} />;
}
export function CardHeader({ className, ...props }) {
  return <div className={cn("flex items-center gap-3 px-6 py-4 border-b border-line", className)} {...props} />;
}
export function CardTitle({ className, ...props }) {
  return <h3 className={cn("font-display text-xl font-medium tracking-tight text-ink", className)} {...props} />;
}
export function CardBody({ className, ...props }) {
  return <div className={cn("px-6 py-5", className)} {...props} />;
}
