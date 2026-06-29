import * as RT from "@radix-ui/react-tabs";
import { cn } from "../../lib/cn.js";

export const Tabs = RT.Root;
export function TabsList({ className, ...p }) {
  return <RT.List className={cn("inline-flex items-center gap-1 rounded-xl border border-line bg-panel/60 p-1", className)} {...p} />;
}
export function TabsTrigger({ className, ...p }) {
  return <RT.Trigger className={cn("rounded-lg px-4 py-1.5 text-sm font-medium text-ink-dim transition data-[state=active]:bg-gold/15 data-[state=active]:text-gold-2 hover:text-ink focus-visible:outline-none", className)} {...p} />;
}
export const TabsContent = RT.Content;
