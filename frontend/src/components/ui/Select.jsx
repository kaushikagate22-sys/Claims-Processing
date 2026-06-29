import * as RS from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "../../lib/cn.js";

export function Select({ value, onValueChange, options, placeholder = "Select…", className }) {
  return (
    <RS.Root value={value} onValueChange={onValueChange}>
      <RS.Trigger className={cn("inline-flex h-9 items-center justify-between gap-2 rounded-lg border border-line-2 bg-raised px-3 text-sm text-ink hover:border-gold/40 focus:outline-none focus:ring-2 focus:ring-gold/50 transition min-w-0", className)}>
        <RS.Value placeholder={placeholder} />
        <RS.Icon><ChevronDown className="h-4 w-4 text-ink-mut" /></RS.Icon>
      </RS.Trigger>
      <RS.Portal>
        <RS.Content position="popper" sideOffset={6} className="z-50 max-h-72 overflow-hidden rounded-xl border border-line-2 bg-raised shadow-2xl">
          <RS.Viewport className="p-1">
            {options.map((o) => {
              const val = typeof o === "string" ? o : o.value;
              const label = typeof o === "string" ? o : o.label;
              return (
                <RS.Item key={val} value={val} className="relative flex cursor-pointer select-none items-center gap-2 rounded-md px-3 py-1.5 pr-8 text-sm text-ink data-[highlighted]:bg-gold/15 data-[highlighted]:text-gold-2 outline-none">
                  <RS.ItemText>{label}</RS.ItemText>
                  <RS.ItemIndicator className="absolute right-2"><Check className="h-4 w-4" /></RS.ItemIndicator>
                </RS.Item>
              );
            })}
          </RS.Viewport>
        </RS.Content>
      </RS.Portal>
    </RS.Root>
  );
}
