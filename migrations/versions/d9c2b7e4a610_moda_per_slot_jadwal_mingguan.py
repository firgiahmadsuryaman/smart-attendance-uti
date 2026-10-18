"""Tambahkan moda dan tautan per slot jadwal mingguan.

Revision ID: d9c2b7e4a610
Revises: 8f09cae67180
Create Date: 2026-10-18 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "d9c2b7e4a610"
down_revision = "8f09cae67180"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "class_schedules",
        sa.Column("delivery_mode", sa.String(length=20), nullable=False, server_default="OFFLINE"),
    )
    op.add_column("class_schedules", sa.Column("online_url", sa.String(length=500), nullable=True))

    # Pertahankan moda dan tautan pada jadwal yang sudah ada sebelum pertemuan
    # diberi pilihan moda masing-masing.
    op.execute("""
        UPDATE class_schedules
        SET delivery_mode = COALESCE((
            SELECT CASE
                WHEN class_offerings.delivery_mode IN ('ONLINE', 'OFFLINE')
                THEN class_offerings.delivery_mode
                ELSE 'OFFLINE'
            END
            FROM class_offerings
            WHERE class_offerings.id = class_schedules.offering_id
        ), 'OFFLINE')
    """)
    op.execute("""
        UPDATE class_schedules
        SET online_url = (
            SELECT class_offerings.online_url
            FROM class_offerings
            WHERE class_offerings.id = class_schedules.offering_id
        )
        WHERE EXISTS (
            SELECT 1 FROM class_offerings
            WHERE class_offerings.id = class_schedules.offering_id
        )
    """)


def downgrade():
    op.drop_column("class_schedules", "online_url")
    op.drop_column("class_schedules", "delivery_mode")
