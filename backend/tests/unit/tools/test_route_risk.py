from src.tools.route_risk import route_risk


class TestRouteRiskTool:
    def test_is_langchain_tool(self):
        assert hasattr(route_risk, "name")
        assert route_risk.name == "route_risk"

    def test_returns_valid_result(self):
        result = route_risk.invoke({
            "origin_lat": -23.55,
            "origin_lng": -46.63,
            "dest_lat": -22.90,
            "dest_lng": -47.06,
        })
        assert hasattr(result, "risk_level")
        assert hasattr(result, "factors")
        assert hasattr(result, "estimated_delay_hours")

    def test_risk_level_is_valid_value(self):
        result = route_risk.invoke({
            "origin_lat": -23.55,
            "origin_lng": -46.63,
            "dest_lat": -22.90,
            "dest_lng": -47.06,
        })
        assert result.risk_level in ("low", "medium", "high")

    def test_factors_is_list_of_strings(self):
        result = route_risk.invoke({
            "origin_lat": -23.55,
            "origin_lng": -46.63,
            "dest_lat": -22.90,
            "dest_lng": -47.06,
        })
        assert isinstance(result.factors, list)
        for f in result.factors:
            assert isinstance(f, str)

    def test_estimated_delay_non_negative(self):
        result = route_risk.invoke({
            "origin_lat": -23.55,
            "origin_lng": -46.63,
            "dest_lat": -22.90,
            "dest_lng": -47.06,
        })
        assert result.estimated_delay_hours >= 0

    def test_deterministic_same_inputs(self):
        args = {
            "origin_lat": -23.55,
            "origin_lng": -46.63,
            "dest_lat": -21.17,
            "dest_lng": -47.81,
        }
        r1 = route_risk.invoke(args)
        r2 = route_risk.invoke(args)
        assert r1.risk_level == r2.risk_level
        assert r1.estimated_delay_hours == r2.estimated_delay_hours
