"""Analysis sessions and occupancy event provenance.

Adds:
* ``analysis_sessions`` — one row per processed video.
* ``occupancy_events.session_id`` / ``source`` / ``video_ts`` — which run produced
  an event, whether it is real CV output or demo data, and where in the video
  it happened. Existing rows are marked ``LEGACY`` because their origin cannot be
  determined after the fact.
* ``seats.source`` / ``confidence`` — whether a seat was detected by the
  calibration engine, seeded, or created manually.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("camera_id", sa.UUID(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="video"),
        sa.Column("pipeline", sa.String(length=16), nullable=False, server_default="report"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="UPLOADED"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("video_fps", sa.Float(), nullable=True),
        sa.Column("total_frames", sa.Integer(), nullable=True),
        sa.Column("video_duration_s", sa.Float(), nullable=True),
        sa.Column("frame_w", sa.Integer(), nullable=True),
        sa.Column("frame_h", sa.Integer(), nullable=True),
        sa.Column("frames_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frames_inferred", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_inference_ms", sa.Float(), nullable=True),
        sa.Column("calibration_s", sa.Float(), nullable=True),
        sa.Column("seat_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_sessions_id", "analysis_sessions", ["id"])
    op.create_index("ix_analysis_sessions_camera_id", "analysis_sessions", ["camera_id"])

    with op.batch_alter_table("occupancy_events") as batch:
        batch.add_column(sa.Column("session_id", sa.UUID(), nullable=True))
        batch.add_column(sa.Column("source", sa.String(length=16), nullable=False, server_default="LEGACY"))
        batch.add_column(sa.Column("video_ts", sa.Float(), nullable=True))
        batch.create_foreign_key(
            "fk_occupancy_events_session_id", "analysis_sessions", ["session_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_occupancy_events_session_id", ["session_id"])
        batch.create_index("ix_occupancy_events_source", ["source"])

    with op.batch_alter_table("seats") as batch:
        batch.add_column(sa.Column("source", sa.String(length=16), nullable=False, server_default="MANUAL"))
        batch.add_column(sa.Column("confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("seats") as batch:
        batch.drop_column("confidence")
        batch.drop_column("source")

    with op.batch_alter_table("occupancy_events") as batch:
        batch.drop_index("ix_occupancy_events_source")
        batch.drop_index("ix_occupancy_events_session_id")
        batch.drop_constraint("fk_occupancy_events_session_id", type_="foreignkey")
        batch.drop_column("video_ts")
        batch.drop_column("source")
        batch.drop_column("session_id")

    op.drop_index("ix_analysis_sessions_camera_id", table_name="analysis_sessions")
    op.drop_index("ix_analysis_sessions_id", table_name="analysis_sessions")
    op.drop_table("analysis_sessions")
