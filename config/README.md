# Doctrine Configuration

This document lists the Doctrine Engine pipeline parameters exposed through `src/doctrine_engine/config/settings.py`.

## Existing top-level settings

| Parameter | Default | Controls |
| --- | --- | --- |
| `universe_min_price` | `5` | Minimum stock price allowed into the Doctrine universe and signal gating. |
| `universe_max_price` | `50` | Maximum stock price allowed into the Doctrine universe and signal gating. |
| `universe_min_avg_volume_20d` | `500000` | Minimum 20-day average share volume for universe eligibility. |
| `universe_min_avg_dollar_volume_20d` | `5000000` | Minimum 20-day average dollar volume for universe eligibility. |
| `polygon_universe_refresh_limit` | `200` | Maximum symbols refreshed and selected per pipeline run. |
| `phase2_history_window_bars` | `20` | History window used by loaders and outcome time barrier tracking. |
| `alert_cooldown_minutes` | `60` | Alert cooldown window applied by the Telegram workflow. |

## `doctrine.signal`

| Parameter | Default | Controls |
| --- | --- | --- |
| `signal_version` | `v1` | Version stamped onto signal results. |
| `long_confidence_threshold` | `0.70` | Minimum confidence required for a `LONG` signal. |
| `fail_closed_event_risk` | `false` | Whether incomplete event-risk coverage blocks signals. |
| `fail_closed_regime` | `false` | Whether incomplete regime coverage blocks signals. |
| `htf_bearish_event_lookback_bars` | `3` | HTF bearish-event lookback before bias is marked bearish. |
| `mtf_invalidation_lookback_bars` | `1` | MTF bearish-event lookback before the setup is invalidated. |
| `ltf_structure_trigger_freshness_bars` | `1` | LTF structure-event freshness window for trigger detection. |
| `micro_trigger_freshness_bars` | `1` | Micro trigger freshness window when micro confirmation is used. |
| `grade_a_plus_threshold` | `0.90` | Minimum confidence for grade `A+`. |
| `grade_a_threshold` | `0.80` | Minimum confidence for grade `A`. |
| `grade_b_threshold` | `0.70` | Minimum confidence for grade `B`. |
| `htf_timeframe` | `4H` | Expected HTF label in signal inputs. |
| `mtf_timeframe` | `1H` | Expected MTF label in signal inputs. |
| `ltf_timeframe` | `15M` | Expected LTF label in signal inputs. |
| `micro_timeframe` | `5M` | Expected micro timeframe label in signal inputs. |
| `htf_bullish_weight` | `0.20` | Confidence weight for bullish HTF bias. |
| `mtf_weight_recontainment` | `0.20` | Confidence weight for `RECONTAINMENT_CANDIDATE`. |
| `mtf_weight_reclaim` | `0.20` | Confidence weight for `BULLISH_RECLAIM`. |
| `mtf_weight_discount` | `0.16` | Confidence weight for `DISCOUNT_RESPONSE`. |
| `mtf_weight_equilibrium` | `0.14` | Confidence weight for `EQUILIBRIUM_HOLD`. |
| `ltf_weight_trap_reverse` | `0.15` | Confidence weight for trap-reverse triggers. |
| `ltf_weight_fake_breakdown` | `0.14` | Confidence weight for fake-breakdown reversals. |
| `ltf_weight_reclaim` | `0.12` | Confidence weight for LTF bullish reclaim. |
| `ltf_weight_choch` | `0.10` | Confidence weight for LTF bullish CHOCH. |
| `ltf_weight_bos` | `0.08` | Confidence weight for LTF bullish BOS. |
| `cross_frame_alignment_bonus` | `0.10` | Bonus applied when HTF/MTF/LTF alignment is valid. |
| `discount_zone_bonus` | `0.05` | Bonus applied when the MTF zone is in discount. |
| `equilibrium_zone_bonus` | `0.03` | Bonus applied when the MTF zone is in equilibrium. |
| `compression_bonus` | `0.03` | Bonus applied when compression is present. |
| `displacement_bonus` | `0.02` | Bonus applied when HTF or MTF displacement is active. |
| `regime_market_permission_strong_threshold` | `0.70` | Strong supportive market-permission threshold. |
| `regime_sector_permission_strong_threshold` | `0.60` | Strong supportive sector-permission threshold. |
| `regime_permission_strong_bonus` | `0.05` | Bonus for strongly supportive regime permissions. |
| `regime_permission_supportive_bonus` | `0.02` | Bonus for merely supportive regime permissions. |
| `sector_strength_bonus_strong` | `0.03` | Sector bonus for `STRONG`. |
| `sector_strength_bonus_neutral` | `0.01` | Sector bonus for `NEUTRAL`. |
| `sector_strength_bonus_weak` | `0.00` | Sector bonus for `WEAK`. |
| `sector_strength_bonus_unknown` | `0.00` | Sector bonus for `UNKNOWN`. |
| `max_event_risk_soft_penalty` | `0.10` | Maximum soft penalty subtracted from signal confidence. |

## `doctrine.ranking`

| Parameter | Default | Controls |
| --- | --- | --- |
| `config_version` | `v1` | Version stamped onto ranking results. |
| `top_threshold` | `0.85` | Minimum score for tier `TOP`. |
| `high_threshold` | `0.75` | Minimum score for tier `HIGH`. |
| `medium_threshold` | `0.65` | Minimum score for tier `MEDIUM`. |
| `min_rr_for_positive_rank` | `1.20` | Minimum RR1 before positive rank bonus applies. |
| `strong_rr1_threshold` | `1.50` | RR1 threshold for the strong RR1 bonus. |
| `strong_rr2_threshold` | `2.50` | RR2 threshold for the strong RR2 bonus. |
| `min_risk_distance` | `0.05` | Minimum confirmation-to-invalidation distance accepted by ranking. |
| `grade_weight_a_plus` | `0.22` | Baseline score weight for grade `A+`. |
| `grade_weight_a` | `0.16` | Baseline score weight for grade `A`. |
| `grade_weight_b` | `0.08` | Baseline score weight for grade `B`. |
| `confidence_multiplier` | `0.30` | Multiplier applied to signal confidence in ranking baseline. |
| `setup_weight_recontainment` | `0.15` | Baseline setup weight for `RECONTAINMENT_CONFIRMED`. |
| `setup_weight_reclaim` | `0.12` | Baseline setup weight for `BULLISH_RECLAIM`. |
| `setup_weight_discount` | `0.10` | Baseline setup weight for `DISCOUNT_RESPONSE`. |
| `setup_weight_equilibrium` | `0.08` | Baseline setup weight for `EQUILIBRIUM_HOLD`. |
| `entry_weight_confirmation` | `0.08` | Entry-type baseline weight for confirmation entries. |
| `entry_weight_base` | `0.05` | Entry-type baseline weight for base entries. |
| `entry_weight_aggressive` | `0.03` | Entry-type baseline weight for aggressive entries. |
| `regime_bonus_bullish_trend` | `0.08` | Final-score bonus for bullish-trend regimes. |
| `regime_bonus_weak_drift` | `0.04` | Final-score bonus for weak-drift regimes. |
| `regime_penalty_chop` | `0.04` | Final-score penalty for chop regimes. |
| `regime_penalty_high_vol_expansion` | `0.08` | Final-score penalty for high-volatility expansion. |
| `sector_bonus_strong` | `0.06` | Final-score bonus for strong sector regime. |
| `sector_penalty_weak` | `0.05` | Final-score penalty for weak sector regime. |
| `market_permission_multiplier` | `0.10` | Weight applied to market permission score. |
| `sector_permission_multiplier` | `0.08` | Weight applied to sector permission score. |
| `rr1_bonus_strong` | `0.10` | Bonus for strong RR1 setups. |
| `rr1_bonus_positive` | `0.05` | Bonus for acceptable RR1 setups. |
| `rr1_penalty_weak` | `0.08` | Penalty for weak RR1 setups. |
| `rr2_bonus_strong` | `0.06` | Bonus for strong RR2 setups. |
| `confirmation_entry_bonus` | `0.03` | Bonus for confirmation entries. |
| `aggressive_entry_penalty` | `0.02` | Penalty for aggressive entries. |
| `trail_structural_bonus` | `0.03` | Bonus when trail mode is structural. |
| `partial_coverage_penalty` | `0.03` | Penalty when regime or event-risk coverage is partial. |

## `doctrine.alert`

| Parameter | Default | Controls |
| --- | --- | --- |
| `sendable_grades` | `["A+", "A"]` | Which grades are eligible for Telegram delivery. |
| `suppress_event_risk_blocked` | `true` | Whether event-risk blocked signals are always suppressed. |

## `doctrine.runner`

| Parameter | Default | Controls |
| --- | --- | --- |
| `config_version` | `v1` | Version stamped onto runner config. |
| `run_mode` | `ONCE` | Default run mode for pipeline execution. |
| `fail_fast` | `false` | Abort the run on the first failed symbol. |
| `continue_on_symbol_error` | `true` | Continue after symbol-level failures. |
| `max_symbol_failures_before_abort` | `25` | Abort threshold for failed symbols. |
| `external_read_retry_attempts` | `2` | External read retry attempts per loader call. |
| `external_read_retry_backoff_ms` | `250` | Backoff between external read retries. |
| `require_micro_confirmation` | `false` | Require 5M confirmation before a signal can be `LONG`. |
| `enable_ranking` | `true` | Enable ranking after trade-plan generation. |
| `enable_alert_workflow` | `true` | Enable alert workflow and rendering. |
| `enable_snapshot_requests` | `false` | Enable snapshot-render requests for sendable alerts. |
| `htf_timeframe` | `4H` | Runner HTF label used when building signal input frames. |
| `mtf_timeframe` | `1H` | Runner MTF label used when building signal input frames. |
| `ltf_timeframe` | `15M` | Runner LTF label used when building signal input frames. |
| `micro_timeframe` | `5M` | Runner micro timeframe label used when requested. |
