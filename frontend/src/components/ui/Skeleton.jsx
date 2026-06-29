import { cn } from "../../lib/cn.js";
export function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-md bg-line/60", className)} />;
}
