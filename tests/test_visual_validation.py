"""Visual validation agent: photos checked against the claim via the reusable vision tool."""
import os
from config.settings import load_rules
from domain.agents.claims_orchestrator import ClaimsPipeline

CLAIM = "data/sample_claims/warranty_clean.txt"


def _imgs(tmp_path):
    ps = []
    for n in ("a.jpg", "b.jpg"):
        p = tmp_path / n; p.write_bytes(b"\xff\xd8\xff\xe0fake"); ps.append(str(p))
    return ps


def test_no_photos_does_not_penalise():
    load_rules.cache_clear()
    r = ClaimsPipeline().process(source_path=CLAIM).model_dump(mode="json")
    assert r["visual_validation"]["assessed"] is False
    assert r["adjudication"]["decision"] == "APPROVED"


def test_mismatching_photos_escalate(tmp_path, monkeypatch):
    load_rules.cache_clear()
    monkeypatch.setenv("VISION_MOCK", "mismatch")
    r = ClaimsPipeline().process(source_path=CLAIM, image_paths=_imgs(tmp_path)).model_dump(mode="json")
    assert r["adjudication"]["decision"] == "ESCALATE"
    fails = {o["id"] for o in r["adjudication"]["rule_outcomes"] if not o["passed"]}
    assert "photo_consistent" in fails
    assert r["visual_validation"]["mismatches"]


def test_matching_photos_approve(tmp_path, monkeypatch):
    load_rules.cache_clear()
    monkeypatch.setenv("VISION_MOCK", "match")
    r = ClaimsPipeline().process(source_path=CLAIM, image_paths=_imgs(tmp_path)).model_dump(mode="json")
    assert r["adjudication"]["decision"] == "APPROVED"
    assert r["visual_validation"]["consistent"] is True
    checks = r["visual_validation"]["checks"]
    assert len(checks) == 3 and all(c["pass"] for c in checks)  # per-criterion observations
