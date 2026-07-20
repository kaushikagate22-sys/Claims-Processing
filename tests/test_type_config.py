"""Config-driven type registry tests."""
from domain.type_config import supported_types, extraction_schema_for

NEW = {"warranty", "nepi", "parts_replacement", "transit_damage", "employee_reimbursement", "nepi_reimbursement"}

def test_supported_types_match_config():
    assert set(supported_types()) == NEW

def test_every_type_has_base_fields():
    for t in supported_types():
        s = extraction_schema_for(t)
        assert "claimant_name" in s and "claim_amount" in s

def test_schema_is_type_specific():
    assert "machine_serial_number" in extraction_schema_for("warranty")
    assert "employee_id" in extraction_schema_for("employee_reimbursement")
    assert "consignment_note" in extraction_schema_for("transit_damage")

def test_unknown_type_falls_back_to_base_only():
    s = extraction_schema_for("does_not_exist")
    assert "claimant_name" in s and "machine_serial_number" not in s
