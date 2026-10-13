from toronto_volunteer_hub.schema import Event


def test_event_defaults_are_not_stated() -> None:
    e = Event(id="x:1", source="x", title="T", url="https://e.x", start="2026-10-18T10:00:00-04:00")
    d = e.to_dict()
    assert d["credit"] == "not-stated"
    assert d["min_age"] is None
    assert d["evidence"] == []
