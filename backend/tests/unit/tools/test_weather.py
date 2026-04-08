from src.tools.weather import weather


class TestWeatherTool:
    def test_is_langchain_tool(self):
        assert hasattr(weather, "name")
        assert weather.name == "weather"

    def test_returns_valid_result(self):
        result = weather.invoke({"lat": -23.55, "lng": -46.63})
        assert hasattr(result, "condition")
        assert hasattr(result, "severity")
        assert hasattr(result, "description")

    def test_severity_is_valid_value(self):
        result = weather.invoke({"lat": -23.55, "lng": -46.63})
        assert result.severity in ("none", "low", "medium", "high")

    def test_deterministic_same_inputs(self):
        r1 = weather.invoke({"lat": -22.90, "lng": -47.06})
        r2 = weather.invoke({"lat": -22.90, "lng": -47.06})
        assert r1.severity == r2.severity
        assert r1.condition == r2.condition

    def test_fields_are_strings(self):
        result = weather.invoke({"lat": -23.55, "lng": -46.63})
        assert isinstance(result.condition, str)
        assert isinstance(result.description, str)
