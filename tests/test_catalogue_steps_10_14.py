from pathlib import Path
import json
import pytest

from src.catalogue.store import CatalogueStore
from src.catalogue.cover import CoverBuilder
from src.catalogue.print_export import PrintExporter
from src.catalogue.digital import DigitalCatalogueBuilder


def _manifest():
    return {"title":"Autumn","subtitle":"2026","locale":"en-GB","format":"A4",
            "products":[{"product_line_id":1,"name":"Fox","description":"A fox","product_url":"/fox"}]}


def _record():
    return {"product_id":"P1","variant_id":"V1","display_name":"Fox",
            "mandatory_features":{"ears":2},"handed_features":{"heart":"left_chest"},
            "silhouette_class":"fox","pattern_topology":"plain",
            "material_class":"crochet","colours":["orange"]}


def _obs():
    return {"features":{"ears":2},"handed_features":{"heart":"left_chest"},
            "silhouette_class":"fox","pattern_topology":"plain",
            "material_class":"crochet","colours":["orange"]}


def _setup(store):
    e=store.create(_manifest(),"tester")
    pm=store.create_product_master(1,_record(),"pm","tester")
    store.approve_product_master(pm["id"],"tester")
    mv=store.create_asset(e["id"],"MASTER_VISUAL",1,"fox.png","mv","tester",source_record_version="1")
    store.validate_product_identity(mv["id"],_obs(),"tester")
    mv=store.lock_master_visual(mv["id"],"tester")
    page=store.create_asset(e["id"],"PAGE",1,"page.html","pagehash","tester",
      {"page_number":1,"composition_manifest":{"page_number":1,"display_name":"Fox","product_id":"P1","description":"A fox"}},"1")
    return e,pm,mv,page


def _to_interior_locked(store,eid):
    for s in ("INTERIOR_BUILDING","INTERIOR_VALIDATING","INTERIOR_LOCKED"):
        store.transition(eid,s,"tester")


def test_cover_requires_interior_lock(tmp_path):
    s=CatalogueStore(tmp_path/"c.sqlite");e,pm,mv,page=_setup(s)
    b=CoverBuilder(s,tmp_path/"out")
    with pytest.raises(ValueError,match="INTERIOR_LOCKED"):
        b.build(e["id"],{"logo_uri":"logo.png","logo_sha256":"logo"},"tester",mv["id"])
    _to_interior_locked(s,e["id"])
    a=b.build(e["id"],{"logo_uri":"logo.png","logo_sha256":"logo"},"tester",mv["id"])
    assert a["asset_type"]=="COVER"
    assert Path(a["uri"]).exists()


def test_print_export_writes_valid_pdf_and_manifest(tmp_path):
    s=CatalogueStore(tmp_path/"c.sqlite");e,pm,mv,page=_setup(s);_to_interior_locked(s,e["id"])
    s.transition(e["id"],"COVER_BUILDING","tester")
    cover=CoverBuilder(s,tmp_path/"out").build(e["id"],{"logo_uri":"logo.png","logo_sha256":"logo"},"tester",mv["id"])
    s.transition(e["id"],"COVER_VALIDATING","tester")
    export=PrintExporter(s,tmp_path/"out").export(e["id"],"tester")
    data=Path(export["uri"]).read_bytes()
    assert data.startswith(b"%PDF-1.4")
    manifest=json.loads((tmp_path/"out"/str(e["id"])/"print_export_manifest.json").read_text())
    assert manifest["export_sha256"]==export["sha256"]


def test_digital_catalogue_has_lazy_loading_and_deep_links(tmp_path):
    s=CatalogueStore(tmp_path/"c.sqlite");e,pm,mv,page=_setup(s)
    asset=DigitalCatalogueBuilder(s,tmp_path/"out").build(e["id"],"tester")
    text=Path(asset["uri"]).read_text()
    assert 'loading="lazy"' in text
    assert 'id="product-1"' in text
    assert asset["metadata"]["format"]=="DIGITAL_HTML"


def test_true_360_rejects_independent_ai_frames(tmp_path):
    s=CatalogueStore(tmp_path/"c.sqlite");e,pm,mv,page=_setup(s)
    with pytest.raises(ValueError,match="Canonical 3D or physical turntable"):
        s.register_360(e["id"],1,{"source":"AI_GENERATED","frame_count":24,"step_deg":15,
          "frame_hashes":["x"]*24},"tester")


def test_true_360_accepts_validated_canonical_3d(tmp_path):
    s=CatalogueStore(tmp_path/"c.sqlite");e,pm,mv,page=_setup(s)
    a=s.create_asset(e["id"],"CANONICAL_3D",1,"fox.glb","glbhash","tester",
      {"format":"GLB","physical_scale_unit":"mm","pivot":"bbox_center",
       "geometry_hash":"geo","materials_hash":"mat"},"1")
    report={"asset_sha256":"glbhash","policy_version":"3d-v1","validator_id":"3d-struct",
            "validator_version":"1","decision":"PASS","checks":[{"id":"3D","status":"PASS"}],
            "evidence":{"geometry_hash":"geo"},"method":"EXACT"}
    s.add_validation(a["id"],report,"tester")
    frames=[f"h{i}" for i in range(24)]
    m=s.register_360(e["id"],1,{"source":"CANONICAL_3D","canonical_3d_asset_id":a["id"],
      "frame_count":24,"step_deg":15,"frame_hashes":frames},"tester")
    assert m["manifest"]["frame_count"]==24
