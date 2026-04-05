import pytest
from src.world.physics import (
    calculate_distance_km,
    calculate_eta_ticks,
    calculate_degradation_delta,
    calculate_breakdown_risk,
    is_trip_blocked,
    calculate_maintenance_ticks,
    evaluate_replenishment_trigger,
)


class TestCalculateDistanceKm:
    def test_campinas_to_sorocaba_approx_100km(self):
        distance = calculate_distance_km(-22.9056, -47.0608, -23.5015, -47.4526)
        assert 90 <= distance <= 110

    def test_same_point_returns_zero(self):
        distance = calculate_distance_km(-22.9056, -47.0608, -22.9056, -47.0608)
        assert distance == pytest.approx(0.0, abs=0.001)

    def test_returns_float(self):
        distance = calculate_distance_km(-22.9056, -47.0608, -23.5015, -47.4526)
        assert isinstance(distance, float)


class TestCalculateEtaTicks:
    def test_120km_at_60kmh_returns_2_ticks(self):
        assert calculate_eta_ticks(120.0, 60.0) == 2

    def test_50km_at_60kmh_rounds_up_to_1_tick(self):
        assert calculate_eta_ticks(50.0, 60.0) == 1

    def test_zero_distance_returns_minimum_1_tick(self):
        assert calculate_eta_ticks(0.0) == 1

    def test_default_speed_is_60kmh(self):
        assert calculate_eta_ticks(120.0) == 2

    def test_61km_at_60kmh_rounds_up_to_2_ticks(self):
        assert calculate_eta_ticks(61.0, 60.0) == 2

    def test_custom_speed(self):
        assert calculate_eta_ticks(90.0, 90.0) == 1


class TestCalculateDegradationDelta:
    def test_full_load_generates_larger_delta_than_half_load(self):
        delta_full = calculate_degradation_delta(500.0, 20.0, 20.0)
        delta_half = calculate_degradation_delta(500.0, 10.0, 20.0)
        assert delta_full > delta_half

    def test_zero_distance_returns_zero(self):
        assert calculate_degradation_delta(0.0, 20.0, 20.0) == pytest.approx(0.0)

    def test_returns_float(self):
        result = calculate_degradation_delta(100.0, 10.0, 20.0)
        assert isinstance(result, float)

    def test_positive_delta_for_positive_distance(self):
        result = calculate_degradation_delta(100.0, 10.0, 20.0)
        assert result > 0.0


class TestCalculateBreakdownRisk:
    def test_zero_degradation_returns_near_zero(self):
        risk = calculate_breakdown_risk(0.0)
        assert risk == pytest.approx(0.0, abs=0.01)

    def test_risk_increases_with_degradation(self):
        assert calculate_breakdown_risk(0.5) < calculate_breakdown_risk(0.8)
        assert calculate_breakdown_risk(0.8) < calculate_breakdown_risk(0.95)

    def test_full_degradation_returns_one(self):
        assert calculate_breakdown_risk(1.0) == pytest.approx(1.0, abs=0.001)

    def test_all_values_clamped_between_0_and_1(self):
        for d in [0.0, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0]:
            risk = calculate_breakdown_risk(d)
            assert 0.0 <= risk <= 1.0

    def test_exponential_growth_above_0_70(self):
        risk_at_70 = calculate_breakdown_risk(0.70)
        risk_at_95 = calculate_breakdown_risk(0.95)
        assert risk_at_95 - risk_at_70 > risk_at_70


class TestIsTripBlocked:
    def test_0_94_not_blocked(self):
        assert is_trip_blocked(0.94) is False

    def test_0_95_is_blocked(self):
        assert is_trip_blocked(0.95) is True

    def test_1_0_is_blocked(self):
        assert is_trip_blocked(1.0) is True

    def test_0_0_not_blocked(self):
        assert is_trip_blocked(0.0) is False


class TestCalculateMaintenanceTicks:
    def test_zero_degradation_returns_2(self):
        assert calculate_maintenance_ticks(0.0) == 2

    def test_full_degradation_returns_24(self):
        assert calculate_maintenance_ticks(1.0) == 24

    def test_half_degradation_between_2_and_24(self):
        result = calculate_maintenance_ticks(0.5)
        assert 2 <= result <= 24

    def test_returns_int(self):
        assert isinstance(calculate_maintenance_ticks(0.5), int)


class TestEvaluateReplenishmentTrigger:
    def test_triggers_when_projected_stock_below_threshold(self):
        # (50 - 20) / 5 = 6.0 < 6 * 1.5 = 9.0 → True
        assert evaluate_replenishment_trigger(
            stock=50, min_stock=20, demand_rate=5, lead_time_ticks=6
        ) is True

    def test_does_not_trigger_with_comfortable_stock(self):
        # (100 - 20) / 5 = 16.0 > 6 * 1.5 = 9.0 → False
        assert evaluate_replenishment_trigger(
            stock=100, min_stock=20, demand_rate=5, lead_time_ticks=6
        ) is False

    def test_zero_demand_rate_always_false(self):
        assert evaluate_replenishment_trigger(
            stock=10, min_stock=5, demand_rate=0, lead_time_ticks=6
        ) is False

    def test_negative_demand_rate_always_false(self):
        assert evaluate_replenishment_trigger(
            stock=10, min_stock=5, demand_rate=-1, lead_time_ticks=6
        ) is False

    def test_custom_safety_factor(self):
        # (50 - 20) / 5 = 6.0 < 6 * 2.0 = 12.0 → True
        assert evaluate_replenishment_trigger(
            stock=50, min_stock=20, demand_rate=5, lead_time_ticks=6, safety_factor=2.0
        ) is True

    def test_default_safety_factor_is_1_5(self):
        # boundary: (50 - 20) / 5 = 6.0, threshold = 6 * 1.5 = 9.0 → triggers
        result = evaluate_replenishment_trigger(
            stock=50, min_stock=20, demand_rate=5, lead_time_ticks=6
        )
        assert result is True
