"""
domain.prompts.templates
=========================
Per-type extraction registry + classification hints for the OEM/dealer
claims rulebook (warranty, NEPI, parts replacement, transit damage,
employee reimbursement).

Per-type *fields* live here (code defaults); per-type *rules* (required
fields, exclusions, escalation triggers, thresholds) live in config/rules.yaml
and can be edited from the Admin screen.
"""
from __future__ import annotations

BASE_EXTRACTION_SCHEMA = {
    "claimant_name": "name of the person/dealer raising the claim (string or null)",
    "claim_reference": "claim number / reference id (string or null)",
    "claim_type": "one of: warranty, nepi, parts_replacement, transit_damage, employee_reimbursement",
    "claim_date": "date the claim was filed, ISO yyyy-mm-dd if possible",
    "claim_amount": "total claimed amount as a number, no currency symbols",
    "description": "one-line description of what is being claimed",
}

TYPE_EXTRACTION_FIELDS = {
    "warranty": {
        "machine_serial_number": "machine serial number (string or null)",
        "model": "machine model (string or null)",
        "hour_meter": "hour meter reading (number or null)",
        "failure_date": "date of failure, ISO yyyy-mm-dd if possible",
        "failure_code": "technician failure/defect code (string or null)",
        "failed_part": "description of the failed part (string or null)",
        "part_serial_number": "serial number of the failed part (string or null)",
        "job_card_number": "job card number (string or null)",
        "labour_hours": "labour hours claimed (number or null)",
        "dealer_name": "dealer / service centre name (string or null)",
    },
    "nepi": {
        "machine_serial_number": "machine serial number (string or null)",
        "model": "machine model (string or null)",
        "dispatch_date": "dispatch date, ISO yyyy-mm-dd if possible",
        "inspection_date": "pre-delivery inspection date, ISO yyyy-mm-dd if possible",
        "handover_status": "pending / conditional / on-hold / accepted (string or null)",
        "issue_type": "transit damage / missing item / cosmetic / functional / doc gap",
        "missing_items": "any missing accessories/tools/manuals (string or null)",
        "rectification_cost": "estimated rectification cost (number or null)",
    },
    "parts_replacement": {
        "part_number": "spare part number (string or null)",
        "batch_number": "part batch number (string or null)",
        "part_serial_number": "part serial number (string or null)",
        "machine_serial_number": "machine serial number it was fitted to (string or null)",
        "fitting_date": "date the part was fitted, ISO yyyy-mm-dd if possible",
        "failure_description": "description of the part failure (string or null)",
        "purchase_invoice": "part purchase invoice / issue slip number (string or null)",
        "rma_number": "return / RMA note number (string or null)",
    },
    "transit_damage": {
        "consignment_note": "LR / consignment note number (string or null)",
        "delivery_challan": "delivery challan number (string or null)",
        "vehicle_number": "transport vehicle number (string or null)",
        "transporter_name": "transporter name (string or null)",
        "machine_serial_number": "machine/part serial number (string or null)",
        "damage_type": "cosmetic / structural / functional / missing / leakage",
        "damage_location": "where on the machine the damage is (string or null)",
        "receipt_remarks": "remarks recorded at receipt/unloading (string or null)",
    },
    "employee_reimbursement": {
        "employee_id": "employee id (string or null)",
        "expense_type": "fuel / toll / lodging / meals / conveyance (string or null)",
        "visit_purpose": "official purpose of the trip/visit (string or null)",
        "travel_dates": "travel/visit dates (string or null)",
        "manager_approval": "is there a manager approval? yes/no/null",
        "distance_km": "distance travelled in km (number or null)",
        "receipts": "receipt/bill reference numbers (string or null)",
    },
}

CLAIM_TYPE_KEYWORDS = {
    "warranty": ["warranty", "failure", "failed part", "job card", "hour meter", "defect", "technician", "repair"],
    "nepi": ["pre-inspection", "pre-delivery", "nepi", "handover", "dispatch", "inspection checklist", "before delivery", "pdi"],
    "parts_replacement": ["spare part", "part replacement", "rma", "part number", "defective part", "batch", "replacement part"],
    "transit_damage": ["transit", "transport", "consignment", "lr ", "delivery challan", "unloading", "damage during transport", "e-way"],
    "employee_reimbursement": ["reimbursement", "expense", "travel claim", "fuel", "toll", "hotel", "meal", "conveyance", "employee"],
}

EXTRACTION_INSTRUCTIONS = (
    "You are extracting fields from a dealer/OEM claim form. "
    "Be literal; do not infer values that are not stated."
)
CLASSIFY_INSTRUCTIONS = (
    "Classify the claim into exactly one of the allowed claim types. "
    "Answer 'unknown' only if none clearly fit."
)
CLAIM_EXTRACTION_SCHEMA = BASE_EXTRACTION_SCHEMA  # back-compat alias
