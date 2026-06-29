import { cn } from "../../lib/cn.js";
export function Table({ className, ...p }) { return <table className={cn("w-full text-base", className)} {...p} />; }
export function THead({ className, ...p }) { return <thead className={cn("text-left text-xs uppercase tracking-wider text-ink-mut", className)} {...p} />; }
export function TR({ className, ...p }) { return <tr className={cn("border-b border-line last:border-0", className)} {...p} />; }
export function TH({ className, ...p }) { return <th className={cn("px-4 py-2.5 font-semibold", className)} {...p} />; }
export function TD({ className, ...p }) { return <td className={cn("px-4 py-3", className)} {...p} />; }
