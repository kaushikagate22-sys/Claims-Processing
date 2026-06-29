// Display helpers + human-readable labels for the engine's rule ids.

export function money(n) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export function pct(n) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return Math.round(Number(n) * 100) + "%";
}

export function dateTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch (_) {
    return iso;
  }
}

// Decision -> palette key used for badges/spines.
export const DECISION_TONE = {
  APPROVED: "approve",
  HOLD: "hold",
  ESCALATE: "escalate",
  REJECTED: "reject",
};

export const DECISION_LABEL = {
  APPROVED: "Approved",
  HOLD: "Hold",
  ESCALATE: "Escalate",
  REJECTED: "Rejected",
};

// Friendly label + category for each rule id the engine emits.
export const RULE_META = {
  amount_positive:            { label: "Claim amount is positive",          cat: "Eligibility" },
  not_excluded:               { label: "Cause not excluded by policy",      cat: "Eligibility" },
  not_duplicate:              { label: "Not a duplicate claim",             cat: "Eligibility" },
  documents_complete:         { label: "Mandatory documents complete",      cat: "Completeness" },
  within_value_authority:     { label: "Within approval authority",         cat: "Review" },
  no_escalation_trigger:      { label: "No escalation trigger",             cat: "Review" },
  machine_serial_present:     { label: "Machine serial number present",     cat: "Completeness" },
  failure_code_present:       { label: "Failure code present",              cat: "Completeness" },
  job_card_present:           { label: "Job card number present",           cat: "Completeness" },
  failed_part_present:        { label: "Failed part present",               cat: "Completeness" },
  inspection_before_handover: { label: "Inspection before handover",        cat: "Eligibility" },
  inspection_date_present:    { label: "Inspection date present",           cat: "Completeness" },
  issue_type_present:         { label: "Issue type present",                cat: "Completeness" },
  dispatch_before_inspection: { label: "Dispatch precedes inspection",      cat: "Completeness" },
  part_number_present:        { label: "Part number present",               cat: "Completeness" },
  invoice_present:            { label: "Purchase invoice present",          cat: "Completeness" },
  failure_desc_present:       { label: "Failure description present",       cat: "Completeness" },
  rma_present:                { label: "Return/RMA reference present",       cat: "Completeness" },
  consignment_present:        { label: "LR/consignment note present",       cat: "Completeness" },
  damage_type_present:        { label: "Damage type present",               cat: "Completeness" },
  receipt_remarks_present:    { label: "Receipt remarks present",           cat: "Completeness" },
  employee_id_present:        { label: "Employee ID present",               cat: "Completeness" },
  expense_type_present:       { label: "Expense type present",              cat: "Completeness" },
  manager_approval_ok:        { label: "Manager approval granted",          cat: "Completeness" },
  dealer_in_master:           { label: "Dealer found in master",            cat: "Record" },
  serial_in_master:           { label: "Machine serial found in master",    cat: "Record" },
  warranty_active_check:      { label: "Warranty active for machine",       cat: "Record" },
  part_in_master:             { label: "Part found in master",              cat: "Record" },
  consignment_in_master:      { label: "Consignment found in master",       cat: "Record" },
  employee_in_master:         { label: "Employee found in master",          cat: "Record" },
  employee_is_active:         { label: "Employee is active",                cat: "Record" },
  within_reimb_limit:         { label: "Within reimbursement limit",        cat: "Record" },
};

export function ruleLabel(id) {
  return RULE_META[id]?.label || id.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function ruleCategory(id) {
  return RULE_META[id]?.cat || "Other";
}

export function severityLabel(sev) {
  if (sev === "reject") return "Reject";
  if (sev === "hold") return "Hold";
  if (sev === "escalate") return "Escalate";
  return "Info";
}

// What the rule guards (shown, muted, when the rule PASSES).
export function severityRole(sev) {
  if (sev === "reject") return "Blocking";
  if (sev === "hold") return "Required";
  if (sev === "escalate") return "Review";
  return "Info";
}

// Badge colour key for a FAILED rule (the consequence it triggers).
export function severityTone(sev) {
  if (sev === "reject") return "reject";
  if (sev === "escalate") return "escalate";
  if (sev === "hold") return "hold";
  return "muted";
}
