"""Tests for probe registry."""

from model_identity_verifier.probes.registry import list_probes, validate_registry


def test_probe_registry_validates() -> None:
    errors = validate_registry()
    assert errors == []


def test_probe_ids_unique() -> None:
    probes = list_probes()
    ids = [p.id for p in probes]
    assert len(ids) == len(set(ids))


def test_probe_count() -> None:
    probes = list_probes()
    assert len(probes) >= 10
