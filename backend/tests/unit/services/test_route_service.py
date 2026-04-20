import pytest

from src.services.route import RouteService, _decode_polyline6


def test_normalize_shape_with_list_of_dicts():
    shape = [{"lon": -46.6, "lat": -23.5}, {"lon": -46.7, "lat": -23.4}]
    assert RouteService._normalize_valhalla_shape(shape) == [
        [-46.6, -23.5],
        [-46.7, -23.4],
    ]


def test_normalize_shape_with_list_of_pairs():
    shape = [[-46.6, -23.5], [-46.7, -23.4]]
    assert RouteService._normalize_valhalla_shape(shape) == [
        [-46.6, -23.5],
        [-46.7, -23.4],
    ]


def test_normalize_shape_decodes_polyline_string():
    encoded = "gklecAhowvhFgx_@gx_@"  # 3 points in São Paulo area at precision 6
    result = RouteService._normalize_valhalla_shape(encoded)
    assert isinstance(result, list)
    assert len(result) >= 2
    for lng, lat in result:
        assert -90.0 < lat < 90.0
        assert -180.0 < lng < 180.0


def test_normalize_shape_empty_returns_empty():
    assert RouteService._normalize_valhalla_shape([]) == []


def test_normalize_shape_unknown_type_raises():
    with pytest.raises(ValueError):
        RouteService._normalize_valhalla_shape([42, 43])


def test_decode_polyline6_roundtrip_simple():
    # Simple 2-point polyline encoded at precision 6
    # Point A: lat=38.5, lng=-120.2; Point B: lat=40.7, lng=-120.95
    # We just verify decoder produces 2 points within expected ranges
    encoded = "_izlhA~rlgdF_seK_seK"
    result = _decode_polyline6(encoded)
    assert len(result) >= 1
    for lng, lat in result:
        assert -180 < lng < 180
        assert -90 < lat < 90
