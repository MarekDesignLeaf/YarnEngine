import pytest
from src.catalogue.store import CatalogueStore


def manifest():
    return {"title":"Test","subtitle":"","locale":"en-GB","format":"A4","products":[]}


def test_catalogue_state_machine_is_fail_closed(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    assert e["state"]=="DRAFT"
    with pytest.raises(ValueError):
        s.transition(e["id"],"RELEASE_APPROVED","tester")
    assert s.get(e["id"])["state"]=="DRAFT"


def test_catalogue_happy_path_and_audit(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    states=["INTERIOR_BUILDING","INTERIOR_VALIDATING","INTERIOR_LOCKED","COVER_BUILDING",
            "COVER_VALIDATING","FINAL_VALIDATING","RELEASE_APPROVED","EXPORTED"]
    for state in states:
        e=s.transition(e["id"],state,"tester")
    assert e["state"]=="EXPORTED"
    events=s.events(e["id"])
    assert len(events)==1+len(states)
    assert events[-1]["to_state"]=="EXPORTED"


def test_failed_catalogue_requires_correction(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    for state in ["INTERIOR_BUILDING","INTERIOR_VALIDATING","FAILED","CORRECTING","INTERIOR_VALIDATING"]:
        e=s.transition(e["id"],state,"tester")
    assert e["state"]=="INTERIOR_VALIDATING"
