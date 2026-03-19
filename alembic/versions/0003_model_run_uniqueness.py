"""normalize model_runs to one row per model/version

Revision ID: 0003_model_run_uniqueness
Revises: 0002_signal_timestamp_uniqueness
Create Date: 2026-03-20 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0003_model_run_uniqueness"
down_revision = "0002_signal_timestamp_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                model_name,
                model_version,
                promoted,
                promoted_at,
                training_window_start,
                training_window_end,
                validation_window_start,
                validation_window_end,
                artifact_uri,
                notes,
                created_at,
                updated_at,
                ROW_NUMBER() OVER (
                    PARTITION BY model_name, model_version
                    ORDER BY
                        COALESCE(promoted_at, updated_at, created_at) DESC,
                        updated_at DESC,
                        created_at DESC,
                        id DESC
                ) AS rn
            FROM model_runs
        ),
        aggregates AS (
            SELECT
                keeper.id AS keeper_id,
                BOOL_OR(all_rows.promoted) AS any_promoted,
                MAX(all_rows.promoted_at) AS latest_promoted_at,
                MIN(all_rows.training_window_start) AS merged_training_window_start,
                MAX(all_rows.training_window_end) AS merged_training_window_end,
                MIN(all_rows.validation_window_start) AS merged_validation_window_start,
                MAX(all_rows.validation_window_end) AS merged_validation_window_end,
                MAX(all_rows.artifact_uri) FILTER (WHERE all_rows.artifact_uri IS NOT NULL) AS merged_artifact_uri,
                STRING_AGG(all_rows.notes, E'\n' ORDER BY all_rows.created_at)
                    FILTER (WHERE all_rows.notes IS NOT NULL AND all_rows.notes <> '') AS merged_notes
            FROM ranked keeper
            JOIN model_runs all_rows
                ON all_rows.model_name = keeper.model_name
               AND all_rows.model_version = keeper.model_version
            WHERE keeper.rn = 1
            GROUP BY keeper.id
        )
        UPDATE model_runs AS target
        SET
            promoted = aggregates.any_promoted,
            promoted_at = CASE
                WHEN aggregates.any_promoted THEN COALESCE(target.promoted_at, aggregates.latest_promoted_at)
                ELSE NULL
            END,
            training_window_start = COALESCE(target.training_window_start, aggregates.merged_training_window_start),
            training_window_end = COALESCE(target.training_window_end, aggregates.merged_training_window_end),
            validation_window_start = COALESCE(target.validation_window_start, aggregates.merged_validation_window_start),
            validation_window_end = COALESCE(target.validation_window_end, aggregates.merged_validation_window_end),
            artifact_uri = COALESCE(target.artifact_uri, aggregates.merged_artifact_uri),
            notes = COALESCE(target.notes, aggregates.merged_notes),
            status = CASE
                WHEN aggregates.any_promoted THEN 'PROMOTED'
                ELSE target.status
            END
        FROM aggregates
        WHERE target.id = aggregates.keeper_id
        """
    )

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY model_name, model_version
                    ORDER BY
                        COALESCE(promoted_at, updated_at, created_at) DESC,
                        updated_at DESC,
                        created_at DESC,
                        id DESC
                ) AS rn
            FROM model_runs
        )
        DELETE FROM model_runs
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    op.create_unique_constraint(
        "uq_model_runs_model_name_model_version",
        "model_runs",
        ["model_name", "model_version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_model_runs_model_name_model_version", "model_runs", type_="unique")
