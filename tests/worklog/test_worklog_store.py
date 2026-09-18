"""The log itself: what gets written, what folds together, who may read it."""
import datetime

import pytest

from src.worklog.store import WorkLogStore, fingerprint


@pytest.fixture()
def store(tmp_path):
    s = WorkLogStore(tmp_path / "worklog.sqlite")
    yield s
    s.close()


def add(store, user_id=1, kind="amigurumi", title="Head", request=None, **fields):
    return store.record(user_id=user_id, kind=kind, title=title,
                        request=request or {"a": 1}, result={"ok": True}, **fields)


def test_a_calculation_is_written_down_with_the_figures_a_person_looks_up(store):
    row = add(store, yarn_id="Y", yarn_name="Yarnsmiths Create DK", colour_name="Teal",
              length_m=27.16741497698143, mass_g=9.368074129993596, packages=1,
              stitches=866, pieces=2, hook_mm=3.0)
    assert row["length_m"] == 27.17 and row["mass_g"] == 9.4      # stored as shown
    assert row["packages"] == 1 and row["stitches"] == 866 and row["pieces"] == 2
    assert row["repeat_count"] == 1 and row["private"] == 0
    assert row["yarn_name"] == "Yarnsmiths Create DK"


def test_calculating_the_same_piece_again_does_not_make_a_second_entry(store):
    first = add(store, request={"same": True}, length_m=10)
    again = add(store, request={"same": True}, length_m=10)
    assert again["entry_id"] == first["entry_id"]
    assert again["repeat_count"] == 2
    assert len(store.list(owner_id=1, viewer_id=1)) == 1


def test_a_different_piece_is_a_different_entry(store):
    add(store, request={"a": 1})
    add(store, request={"a": 2})
    add(store, request={"a": 1}, kind="flat")
    assert len(store.list(owner_id=1, viewer_id=1)) == 3
    assert fingerprint("flat", {"a": 1}) != fingerprint("amigurumi", {"a": 1})


def test_last_weeks_identical_piece_stays_its_own_entry(store):
    old = add(store, request={"a": 1})
    stale = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).isoformat()
    store.conn.execute("UPDATE worklog SET updated_at=? WHERE entry_id=?", (stale, old["entry_id"]))
    store.conn.commit()
    again = add(store, request={"a": 1})
    assert again["entry_id"] != old["entry_id"]


def test_a_log_is_invisible_until_its_owner_shares_it(store):
    add(store, user_id=1)
    assert store.list(owner_id=1, viewer_id=2) is None
    assert store.totals(owner_id=1, viewer_id=2) is None
    store.share(1, 2)
    assert len(store.list(owner_id=1, viewer_id=2)) == 1
    store.unshare(1, 2)
    assert store.list(owner_id=1, viewer_id=2) is None


def test_sharing_is_one_person_at_a_time_and_not_contagious(store):
    add(store, user_id=1)
    store.share(1, 2)
    assert store.list(owner_id=1, viewer_id=3) is None        # 3 was never named
    assert store.viewers_of(1) == [2] and store.owners_for(2) == [1]
    assert store.share(1, 1) is False                          # not with yourself


def test_an_entry_marked_private_stays_behind_even_when_the_log_is_shared(store):
    public = add(store, request={"a": 1}, title="Bear head")
    secret = add(store, request={"a": 2}, title="A client's order")
    store.share(1, 2)
    store.update(secret["entry_id"], user_id=1, private=True)
    seen = [e["title"] for e in store.list(owner_id=1, viewer_id=2)]
    assert seen == ["Bear head"]
    assert store.visible_entry(secret["entry_id"], 2) is None
    assert store.visible_entry(secret["entry_id"], 1) is not None
    assert store.visible_entry(public["entry_id"], 2) is not None
    assert store.totals(owner_id=1, viewer_id=2)["entries"] == 1


def test_only_the_owner_can_change_or_delete_an_entry(store):
    row = add(store, user_id=1)
    store.share(1, 2)
    assert store.update(row["entry_id"], user_id=2, note="mine now") is None
    assert store.delete(row["entry_id"], user_id=2) is False
    assert store.update(row["entry_id"], user_id=1, note="ordered 12 May")["note"] == "ordered 12 May"
    assert store.delete(row["entry_id"], user_id=1) is True


def test_searching_and_filtering_a_log(store):
    add(store, request={"a": 1}, title="Bear head", yarn_id="DK", yarn_name="Create DK",
        colour_name="Teal")
    add(store, request={"a": 2}, kind="flat", title="Blanket", yarn_id="ARAN",
        yarn_name="Cotton Aran")
    store.update(store.list(owner_id=1, viewer_id=1)[0]["entry_id"], 1, note="order 214")
    assert len(store.list(owner_id=1, viewer_id=1, kind="flat")) == 1
    assert len(store.list(owner_id=1, viewer_id=1, yarn_id="DK")) == 1
    assert [e["title"] for e in store.list(owner_id=1, viewer_id=1, query="Teal")] == ["Bear head"]
    assert [e["title"] for e in store.list(owner_id=1, viewer_id=1, query="Aran")] == ["Blanket"]
    assert len(store.list(owner_id=1, viewer_id=1, query="214")) == 1


def test_totals_add_up_the_log(store):
    add(store, request={"a": 1}, length_m=10.0, mass_g=4.0, stitches=100)
    add(store, request={"a": 2}, length_m=5.5, mass_g=2.0, stitches=50)
    tot = store.totals(owner_id=1, viewer_id=1)
    assert tot == {"entries": 2, "length_m": 15.5, "mass_g": 6.0, "stitches": 150}


def test_progress_belongs_to_the_maker_and_starts_empty(store):
    row = add(store, user_id=1)
    assert store.progress(row["entry_id"], 1) is None
    assert store.save_progress(row["entry_id"], 2, running=True) is None   # not theirs
    p = store.save_progress(row["entry_id"], 1, current_round=3, done=[1, 2, 3])
    assert p["current_round"] == 3 and p["done"] == [1, 2, 3]
    assert p["elapsed_seconds"] == 0 and p["running_since"] is None


def test_the_clock_banks_time_instead_of_ticking(store):
    import datetime as dt
    row = add(store, user_id=1)
    store.save_progress(row["entry_id"], 1, running=True)
    # pretend the piece was started twenty minutes ago and put down
    started = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20)).isoformat()
    store.conn.execute("UPDATE worklog_progress SET running_since=? WHERE entry_id=?",
                       (started, row["entry_id"]))
    store.conn.commit()
    assert store.progress(row["entry_id"], 1)["elapsed_seconds"] == pytest.approx(1200, abs=5)
    paused = store.save_progress(row["entry_id"], 1, running=False)
    assert paused["running_since"] is None
    assert paused["seconds"] == pytest.approx(1200, abs=5)
    # paused time does not keep growing
    assert store.progress(row["entry_id"], 1)["elapsed_seconds"] == pytest.approx(paused["seconds"])


def test_finishing_a_piece_stops_the_clock(store):
    row = add(store, user_id=1)
    store.save_progress(row["entry_id"], 1, running=True)
    done = store.save_progress(row["entry_id"], 1, finished=True)
    assert done["finished_at"] and done["running_since"] is None
    again = store.save_progress(row["entry_id"], 1, finished=False)
    assert again["finished_at"] is None


def test_a_log_can_show_time_and_how_far_along_without_loading_every_piece(store):
    a = add(store, request={"a": 1}, user_id=1)
    add(store, request={"b": 2}, user_id=1)
    store.save_progress(a["entry_id"], 1, current_round=4, done=[1, 2, 3, 4])
    summary = store.progress_for([a["entry_id"]], 1)
    assert summary[a["entry_id"]]["done_count"] == 4
    assert summary[a["entry_id"]]["current_round"] == 4
    assert store.progress_for([], 1) == {}
