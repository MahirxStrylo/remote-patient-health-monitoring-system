"""initial_ecg_session_and_scalable_keys

Revision ID: 001_initial_ecg_session
Revises: 
Create Date: 2026-11-22 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_ecg_session'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. doctor_users
    op.create_table(
        'doctor_users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=64), nullable=False, unique=True),
        sa.Column('email', sa.String(length=128), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=128), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # 2. patients
    op.create_table(
        'patients',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('patient_id', sa.String(length=64), nullable=False, unique=True),
        sa.Column('full_name', sa.String(length=128), nullable=False),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # 3. devices
    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('api_key_id', sa.String(length=64), nullable=True, unique=True),
        sa.Column('api_key_prefix', sa.String(length=32), nullable=True),
        sa.Column('api_key_hash', sa.String(length=255), nullable=False),
        sa.Column('api_key_revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_batch_id', sa.String(length=128), nullable=True),
        sa.Column('firmware_version', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # 4. ecg_sessions
    op.create_table(
        'ecg_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.String(length=64), nullable=False, unique=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('devices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sampling_rate_hz', sa.Integer(), nullable=False, server_default='250'),
        sa.Column('unit', sa.String(length=32), nullable=False, server_default='adc_counts'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='Recording'),
        sa.Column('total_samples', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_batches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expected_batches', sa.Integer(), nullable=True),
        sa.Column('is_simulated', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('lead_off_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('signal_quality', sa.String(length=32), nullable=True),
        sa.Column('ai_analysis_status', sa.String(length=32), nullable=False, server_default='not_configured'),
        sa.Column('ai_model_name', sa.String(length=128), nullable=True),
        sa.Column('ai_model_version', sa.String(length=64), nullable=True),
        sa.Column('ai_analysis_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ai_classification', sa.String(length=128), nullable=True),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # 5. ecg_batches
    op.create_table(
        'ecg_batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('ecg_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('samples_json', sa.Text(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('signal_quality', sa.String(length=32), nullable=True),
        sa.Column('lead_off', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('session_id', 'sequence_number', name='uq_session_sequence')
    )

    # 6. vital_readings
    op.create_table(
        'vital_readings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('devices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('batch_id', sa.String(length=128), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('heart_rate_bpm', sa.Float(), nullable=True),
        sa.Column('spo2_percent', sa.Float(), nullable=True),
        sa.Column('temperature_c', sa.Float(), nullable=True),
        sa.Column('is_simulated', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # 7. device_uploads
    op.create_table(
        'device_uploads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('devices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('batch_id', sa.String(length=128), nullable=False),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('payload_size_bytes', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='accepted'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # 8. doctor_notes
    op.create_table(
        'doctor_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', sa.Integer(), sa.ForeignKey('doctor_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # 9. audit_events
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('actor_type', sa.String(length=32), nullable=False),
        sa.Column('actor_id', sa.String(length=128), nullable=False),
        sa.Column('resource_type', sa.String(length=64), nullable=False),
        sa.Column('resource_id', sa.String(length=128), nullable=False),
        sa.Column('detail', sa.Text(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('doctor_notes')
    op.drop_table('device_uploads')
    op.drop_table('vital_readings')
    op.drop_table('ecg_batches')
    op.drop_table('ecg_sessions')
    op.drop_table('devices')
    op.drop_table('patients')
    op.drop_table('doctor_users')
