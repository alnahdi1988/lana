from __future__ import annotations

from decimal import Decimal

from doctrine_engine.ranking.models import (
    RankingEngineConfig,
    RankingEngineInput,
    RankingEngineResult,
)


class RankingEngine:
    def __init__(self, config: RankingEngineConfig | None = None) -> None:
        self.config = config or RankingEngineConfig()

    def evaluate(self, ranking_input: RankingEngineInput) -> RankingEngineResult:
        self._validate_input(ranking_input)

        baseline_score = self._baseline_score(ranking_input)
        known_at = ranking_input.signal_result.known_at

        if ranking_input.signal_result.signal != "LONG":
            return self._skipped_result(
                ranking_input=ranking_input,
                ranking_state="SKIPPED_NOT_LONG",
                baseline_score=baseline_score,
                known_at=known_at,
                reason_codes=["RANK_NON_LONG", "RANK_TIER_DO_NOT_QUEUE"],
            )

        if ranking_input.event_risk_result.blocked:
            return self._skipped_result(
                ranking_input=ranking_input,
                ranking_state="SKIPPED_BLOCKED",
                baseline_score=baseline_score,
                known_at=known_at,
                reason_codes=["RANK_EVENT_BLOCKED", "RANK_TIER_DO_NOT_QUEUE"],
            )

        rr1, rr2 = self._trade_plan_ratios(ranking_input)
        final_score = baseline_score
        reason_codes: list[str] = []

        market_regime = ranking_input.regime_result.market_regime
        if market_regime == "BULLISH_TREND":
            final_score += self.config.regime_bonus_bullish_trend
            reason_codes.append("RANK_BULLISH_TREND")
        elif market_regime == "WEAK_DRIFT":
            final_score += self.config.regime_bonus_weak_drift
            reason_codes.append("RANK_WEAK_DRIFT")
        elif market_regime == "CHOP":
            final_score -= self.config.regime_penalty_chop
            reason_codes.append("RANK_CHOP")
        elif market_regime == "HIGH_VOL_EXPANSION":
            final_score -= self.config.regime_penalty_high_vol_expansion
            reason_codes.append("RANK_HIGH_VOL_EXPANSION")

        sector_regime = ranking_input.regime_result.sector_regime
        if sector_regime == "SECTOR_STRONG":
            final_score += self.config.sector_bonus_strong
            reason_codes.append("RANK_SECTOR_STRONG")
        elif sector_regime == "SECTOR_WEAK":
            final_score -= self.config.sector_penalty_weak
            reason_codes.append("RANK_SECTOR_WEAK")

        final_score += self.config.market_permission_multiplier * self._decimal_or_zero(
            ranking_input.regime_result.market_permission_score
        )
        final_score += self.config.sector_permission_multiplier * self._decimal_or_zero(
            ranking_input.regime_result.sector_permission_score
        )
        final_score -= ranking_input.event_risk_result.soft_penalty

        if (
            not ranking_input.regime_result.coverage_complete
            or not ranking_input.event_risk_result.coverage_complete
        ):
            final_score -= self.config.partial_coverage_penalty
            reason_codes.append("RANK_PARTIAL_COVERAGE_PENALTY")

        if rr1 >= Decimal("1.50"):
            final_score += self.config.rr1_bonus_strong
            reason_codes.append("RANK_RR1_STRONG")
        elif rr1 >= self.config.min_rr_for_positive_rank:
            final_score += self.config.rr1_bonus_positive
        else:
            final_score -= self.config.rr1_penalty_weak
            reason_codes.append("RANK_RR1_WEAK")

        if rr2 >= Decimal("2.50"):
            final_score += self.config.rr2_bonus_strong
            reason_codes.append("RANK_RR2_STRONG")

        if ranking_input.trade_plan_result.entry_type == "CONFIRMATION":
            final_score += self.config.confirmation_entry_bonus
            reason_codes.append("RANK_CONFIRMATION_ENTRY")
        elif ranking_input.trade_plan_result.entry_type == "AGGRESSIVE":
            final_score -= self.config.aggressive_entry_penalty
            reason_codes.append("RANK_AGGRESSIVE_ENTRY")

        if ranking_input.trade_plan_result.trail_mode == "STRUCTURAL":
            final_score += self.config.trail_structural_bonus

        final_score = self._clamp_score(final_score)
        ranking_tier = self._tier_from_score(final_score)
        ranking_grade = self._grade_from_tier(ranking_tier)
        ranking_label = self._label_from_ranked_tier(ranking_tier)
        reason_codes.append(self._tier_reason_code(ranking_tier))

        return RankingEngineResult(
            config_version=self.config.config_version,
            signal_id=ranking_input.signal_id,
            symbol_id=ranking_input.signal_result.symbol_id,
            ticker=ranking_input.signal_result.ticker,
            ranking_state="RANKED",
            ranking_tier=ranking_tier,
            ranking_grade=ranking_grade,
            ranking_label=ranking_label,
            baseline_score=baseline_score,
            final_score=final_score,
            reason_codes=reason_codes,
            known_at=known_at,
            extensible_context={
                "rr1": format(rr1, "f"),
                "rr2": format(rr2, "f"),
                "market_regime": ranking_input.regime_result.market_regime,
                "sector_regime": ranking_input.regime_result.sector_regime,
                "stock_structure_quality_score": (
                    format(ranking_input.regime_result.stock_structure_quality_score, "f")
                    if ranking_input.regime_result.stock_structure_quality_score is not None
                    else None
                ),
            },
        )

    def _validate_input(self, ranking_input: RankingEngineInput) -> None:
        signal_result = ranking_input.signal_result
        trade_plan_result = ranking_input.trade_plan_result
        if trade_plan_result.signal_id != ranking_input.signal_id:
            raise ValueError("Trade plan signal_id must match ranking signal_id.")
        if trade_plan_result.symbol_id != signal_result.symbol_id:
            raise ValueError("Trade plan symbol_id must match signal symbol_id.")
        if trade_plan_result.ticker != signal_result.ticker:
            raise ValueError("Trade plan ticker must match signal ticker.")
        if trade_plan_result.plan_timestamp != signal_result.signal_timestamp:
            raise ValueError("Trade plan timestamp must match signal timestamp.")
        if trade_plan_result.known_at != signal_result.known_at:
            raise ValueError("Trade plan known_at must equal signal known_at.")
        if ranking_input.regime_result.known_at > signal_result.known_at:
            raise ValueError("Regime known_at cannot exceed signal known_at.")
        if ranking_input.event_risk_result.known_at > signal_result.known_at:
            raise ValueError("Event-risk known_at cannot exceed signal known_at.")

    def _baseline_score(self, ranking_input: RankingEngineInput) -> Decimal:
        score = Decimal("0.0000")
        grade = ranking_input.signal_result.grade
        if grade == "A+":
            score += self.config.grade_weight_a_plus
        elif grade == "A":
            score += self.config.grade_weight_a
        elif grade == "B":
            score += self.config.grade_weight_b

        score += self.config.confidence_multiplier * ranking_input.signal_result.confidence

        setup_state = ranking_input.signal_result.setup_state
        if setup_state == "RECONTAINMENT_CONFIRMED":
            score += self.config.setup_weight_recontainment
        elif setup_state == "BULLISH_RECLAIM":
            score += self.config.setup_weight_reclaim
        elif setup_state == "DISCOUNT_RESPONSE":
            score += self.config.setup_weight_discount
        elif setup_state == "EQUILIBRIUM_HOLD":
            score += self.config.setup_weight_equilibrium

        entry_type = ranking_input.trade_plan_result.entry_type
        if entry_type == "CONFIRMATION":
            score += self.config.entry_weight_confirmation
        elif entry_type == "BASE":
            score += self.config.entry_weight_base
        elif entry_type == "AGGRESSIVE":
            score += self.config.entry_weight_aggressive

        return self._clamp_score(score)

    def _trade_plan_ratios(self, ranking_input: RankingEngineInput) -> tuple[Decimal, Decimal]:
        trade_plan_result = ranking_input.trade_plan_result
        risk_distance = trade_plan_result.confirmation_level - trade_plan_result.invalidation_level
        if risk_distance < self.config.min_risk_distance:
            raise ValueError("Risk distance is below the configured minimum.")
        if trade_plan_result.tp1 <= trade_plan_result.confirmation_level:
            raise ValueError("TP1 must be above confirmation level.")
        if trade_plan_result.tp2 <= trade_plan_result.tp1:
            raise ValueError("TP2 must be above TP1.")

        reward_1 = trade_plan_result.tp1 - trade_plan_result.confirmation_level
        reward_2 = trade_plan_result.tp2 - trade_plan_result.confirmation_level
        rr1 = (reward_1 / risk_distance).quantize(Decimal("0.0000"))
        rr2 = (reward_2 / risk_distance).quantize(Decimal("0.0000"))
        return rr1, rr2

    def _skipped_result(
        self,
        ranking_input: RankingEngineInput,
        ranking_state: str,
        baseline_score: Decimal,
        known_at,
        reason_codes: list[str],
    ) -> RankingEngineResult:
        ranking_label = "BLOCKED_NON_LONG" if ranking_state == "SKIPPED_NOT_LONG" else "BLOCKED_EVENT_RISK"
        return RankingEngineResult(
            config_version=self.config.config_version,
            signal_id=ranking_input.signal_id,
            symbol_id=ranking_input.signal_result.symbol_id,
            ticker=ranking_input.signal_result.ticker,
            ranking_state=ranking_state,
            ranking_tier="DO_NOT_QUEUE",
            ranking_grade="R0",
            ranking_label=ranking_label,
            baseline_score=baseline_score,
            final_score=Decimal("0.0000"),
            reason_codes=reason_codes,
            known_at=known_at,
            extensible_context={
                "market_regime": ranking_input.regime_result.market_regime,
                "sector_regime": ranking_input.regime_result.sector_regime,
                "stock_structure_quality_score": (
                    format(ranking_input.regime_result.stock_structure_quality_score, "f")
                    if ranking_input.regime_result.stock_structure_quality_score is not None
                    else None
                ),
            },
        )

    def _tier_from_score(self, final_score: Decimal) -> str:
        if final_score == Decimal("0.0000"):
            return "DO_NOT_QUEUE"
        if final_score >= self.config.top_threshold:
            return "TOP"
        if final_score >= self.config.high_threshold:
            return "HIGH"
        if final_score >= self.config.medium_threshold:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _grade_from_tier(ranking_tier: str) -> str:
        return {
            "TOP": "R1",
            "HIGH": "R2",
            "MEDIUM": "R3",
            "LOW": "R4",
            "DO_NOT_QUEUE": "R0",
        }[ranking_tier]

    @staticmethod
    def _label_from_ranked_tier(ranking_tier: str) -> str:
        return {
            "TOP": "BASELINE_TOP",
            "HIGH": "BASELINE_HIGH",
            "MEDIUM": "BASELINE_MEDIUM",
            "LOW": "BASELINE_LOW",
            "DO_NOT_QUEUE": "BASELINE_LOW",
        }[ranking_tier]

    @staticmethod
    def _tier_reason_code(ranking_tier: str) -> str:
        return {
            "TOP": "RANK_TIER_TOP",
            "HIGH": "RANK_TIER_HIGH",
            "MEDIUM": "RANK_TIER_MEDIUM",
            "LOW": "RANK_TIER_LOW",
            "DO_NOT_QUEUE": "RANK_TIER_DO_NOT_QUEUE",
        }[ranking_tier]

    @staticmethod
    def _decimal_or_zero(value: Decimal | None) -> Decimal:
        return value if value is not None else Decimal("0.0000")

    @staticmethod
    def _clamp_score(value: Decimal) -> Decimal:
        return max(Decimal("0.0000"), min(Decimal("1.0000"), value)).quantize(Decimal("0.0000"))
