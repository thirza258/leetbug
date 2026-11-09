"""debugging assessment platform: diagnosis, incidents, mutation testing, adaptive AI, assessments, organizations"""
import sqlalchemy as sa
from alembic import op

revision = 'c4d9e7a1f2b3'
down_revision = 'b2c8e4f19a23'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('actor_id', sa.String(length=36), nullable=True),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_table('quality_gates',
    sa.Column('category', sa.String(length=30), nullable=False),
    sa.Column('thresholds', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=36), nullable=True),
    sa.PrimaryKeyConstraint('category')
    )
    op.create_table('events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('type', sa.String(length=60), nullable=False),
    sa.Column('problem_id', sa.Integer(), nullable=True),
    sa.Column('attempt_id', sa.String(length=36), nullable=True),
    sa.Column('assessment_session_id', sa.String(length=36), nullable=True),
    sa.Column('incident_session_id', sa.String(length=36), nullable=True),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_assessment_session_id'), 'events', ['assessment_session_id'], unique=False)
    op.create_index(op.f('ix_events_attempt_id'), 'events', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_events_created_at'), 'events', ['created_at'], unique=False)
    op.create_index(op.f('ix_events_incident_session_id'), 'events', ['incident_session_id'], unique=False)
    op.create_index(op.f('ix_events_type'), 'events', ['type'], unique=False)
    op.create_index(op.f('ix_events_user_id'), 'events', ['user_id'], unique=False)
    op.create_table('incidents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('problem_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('severity', sa.String(length=10), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=40), nullable=False),
    sa.Column('affected_services', sa.JSON(), nullable=False),
    sa.Column('impact', sa.JSON(), nullable=False),
    sa.Column('expected_behavior', sa.Text(), nullable=False),
    sa.Column('observed_symptoms', sa.JSON(), nullable=False),
    sa.Column('timeline', sa.JSON(), nullable=False),
    sa.Column('artifacts', sa.JSON(), nullable=False),
    sa.Column('scenarios', sa.JSON(), nullable=False),
    sa.Column('evaluation_config', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('problem_id')
    )
    op.create_index(op.f('ix_incidents_category'), 'incidents', ['category'], unique=False)
    op.create_index(op.f('ix_incidents_slug'), 'incidents', ['slug'], unique=True)
    op.create_index(op.f('ix_incidents_status'), 'incidents', ['status'], unique=False)
    op.create_table('mutation_runs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('problem_id', sa.Integer(), nullable=False),
    sa.Column('problem_version', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('language', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('config', sa.JSON(), nullable=False),
    sa.Column('total_mutations', sa.Integer(), nullable=False),
    sa.Column('killed_mutations', sa.Integer(), nullable=False),
    sa.Column('survived_mutations', sa.Integer(), nullable=False),
    sa.Column('timed_out_mutations', sa.Integer(), nullable=False),
    sa.Column('invalid_mutations', sa.Integer(), nullable=False),
    sa.Column('equivalent_mutations', sa.Integer(), nullable=False),
    sa.Column('error_mutations', sa.Integer(), nullable=False),
    sa.Column('mutation_score', sa.Float(), nullable=True),
    sa.Column('gate_status', sa.String(length=20), nullable=True),
    sa.Column('report', sa.JSON(), nullable=False),
    sa.Column('execution_metadata', sa.JSON(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('requested_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mutation_runs_created_at'), 'mutation_runs', ['created_at'], unique=False)
    op.create_index(op.f('ix_mutation_runs_problem_id'), 'mutation_runs', ['problem_id'], unique=False)
    op.create_index(op.f('ix_mutation_runs_status'), 'mutation_runs', ['status'], unique=False)
    op.create_table('organizations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)
    op.create_table('competency_profiles',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=True),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('weights', sa.JSON(), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'slug', name='uq_competency_profile_slug')
    )
    op.create_index(op.f('ix_competency_profiles_organization_id'), 'competency_profiles', ['organization_id'], unique=False)
    op.create_table('incident_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('incident_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('investigation', sa.JSON(), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('scores', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incident_sessions_incident_id'), 'incident_sessions', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_sessions_status'), 'incident_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_incident_sessions_user_id'), 'incident_sessions', ['user_id'], unique=False)
    op.create_table('mutation_cases',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('run_id', sa.String(length=36), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('operator', sa.String(length=40), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.Column('line', sa.Integer(), nullable=True),
    sa.Column('critical', sa.Boolean(), nullable=False),
    sa.Column('original_snippet', sa.Text(), nullable=False),
    sa.Column('mutated_snippet', sa.Text(), nullable=False),
    sa.Column('original_code_hash', sa.String(length=64), nullable=False),
    sa.Column('mutated_code_hash', sa.String(length=64), nullable=False),
    sa.Column('mutated_code', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('failure_classification', sa.String(length=30), nullable=True),
    sa.Column('killing_tests', sa.JSON(), nullable=False),
    sa.Column('is_equivalent', sa.Boolean(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('execution_duration_ms', sa.Float(), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['mutation_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mutation_cases_run_id'), 'mutation_cases', ['run_id'], unique=False)
    op.create_index(op.f('ix_mutation_cases_status'), 'mutation_cases', ['status'], unique=False)
    op.create_table('organization_members',
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('organization_id', 'user_id')
    )
    op.create_index(op.f('ix_organization_members_user_id'), 'organization_members', ['user_id'], unique=False)
    op.create_table('assessments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('assessment_type', sa.String(length=20), nullable=False),
    sa.Column('duration_seconds', sa.Integer(), nullable=False),
    sa.Column('configuration', sa.JSON(), nullable=False),
    sa.Column('scoring_rubric', sa.JSON(), nullable=False),
    sa.Column('assistance_policy', sa.JSON(), nullable=False),
    sa.Column('visibility', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=True),
    sa.Column('competency_profile_id', sa.String(length=36), nullable=True),
    sa.Column('available_from', sa.DateTime(timezone=True), nullable=True),
    sa.Column('available_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['competency_profile_id'], ['competency_profiles.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessments_organization_id'), 'assessments', ['organization_id'], unique=False)
    op.create_index(op.f('ix_assessments_slug'), 'assessments', ['slug'], unique=True)
    op.create_index(op.f('ix_assessments_status'), 'assessments', ['status'], unique=False)
    op.create_table('assessment_invitations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('assessment_id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('invited_by', sa.String(length=36), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('accepted_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['accepted_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_assessment_invitations_assessment_id'), 'assessment_invitations', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_invitations_email'), 'assessment_invitations', ['email'], unique=False)
    op.create_table('assessment_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('assessment_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('invitation_id', sa.String(length=36), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('config_snapshot', sa.JSON(), nullable=False),
    sa.Column('challenge_order', sa.JSON(), nullable=False),
    sa.Column('total_score', sa.Float(), nullable=True),
    sa.Column('scoring_details', sa.JSON(), nullable=False),
    sa.Column('assistance_metadata', sa.JSON(), nullable=False),
    sa.Column('report', sa.JSON(), nullable=True),
    sa.Column('report_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['invitation_id'], ['assessment_invitations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessment_sessions_assessment_id'), 'assessment_sessions', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_sessions_expires_at'), 'assessment_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_assessment_sessions_status'), 'assessment_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_assessment_sessions_user_id'), 'assessment_sessions', ['user_id'], unique=False)
    op.create_table('challenge_attempts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('problem_id', sa.Integer(), nullable=False),
    sa.Column('scope', sa.String(length=80), nullable=False),
    sa.Column('context', sa.String(length=20), nullable=False),
    sa.Column('assessment_session_id', sa.String(length=36), nullable=True),
    sa.Column('incident_session_id', sa.String(length=36), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('solved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('diagnosis_score', sa.Float(), nullable=True),
    sa.Column('correctness_score', sa.Float(), nullable=True),
    sa.Column('quality_score', sa.Float(), nullable=True),
    sa.Column('explanation_score', sa.Float(), nullable=True),
    sa.Column('verification_score', sa.Float(), nullable=True),
    sa.Column('time_score', sa.Float(), nullable=True),
    sa.Column('total_score', sa.Float(), nullable=True),
    sa.Column('scores', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['assessment_session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['incident_session_id'], ['incident_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'problem_id', 'scope', name='uq_attempt_scope')
    )
    op.create_index(op.f('ix_challenge_attempts_assessment_session_id'), 'challenge_attempts', ['assessment_session_id'], unique=False)
    op.create_index(op.f('ix_challenge_attempts_incident_session_id'), 'challenge_attempts', ['incident_session_id'], unique=False)
    op.create_index(op.f('ix_challenge_attempts_problem_id'), 'challenge_attempts', ['problem_id'], unique=False)
    op.create_index(op.f('ix_challenge_attempts_status'), 'challenge_attempts', ['status'], unique=False)
    op.create_index(op.f('ix_challenge_attempts_user_id'), 'challenge_attempts', ['user_id'], unique=False)
    op.create_table('ai_interactions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('problem_id', sa.Integer(), nullable=False),
    sa.Column('attempt_id', sa.String(length=36), nullable=True),
    sa.Column('assessment_session_id', sa.String(length=36), nullable=True),
    sa.Column('intent', sa.String(length=40), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('context_version', sa.String(length=20), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=True),
    sa.Column('context_summary', sa.JSON(), nullable=False),
    sa.Column('retrieval_metadata', sa.JSON(), nullable=False),
    sa.Column('response_metadata', sa.JSON(), nullable=False),
    sa.Column('response', sa.JSON(), nullable=True),
    sa.Column('response_text', sa.Text(), nullable=True),
    sa.Column('sources', sa.JSON(), nullable=False),
    sa.Column('token_usage', sa.Integer(), nullable=True),
    sa.Column('latency_ms', sa.Float(), nullable=True),
    sa.Column('retrieval_ms', sa.Float(), nullable=True),
    sa.Column('generation_ms', sa.Float(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['attempt_id'], ['challenge_attempts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_interactions_assessment_session_id'), 'ai_interactions', ['assessment_session_id'], unique=False)
    op.create_index(op.f('ix_ai_interactions_attempt_id'), 'ai_interactions', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_ai_interactions_created_at'), 'ai_interactions', ['created_at'], unique=False)
    op.create_index(op.f('ix_ai_interactions_problem_id'), 'ai_interactions', ['problem_id'], unique=False)
    op.create_index(op.f('ix_ai_interactions_status'), 'ai_interactions', ['status'], unique=False)
    op.create_index(op.f('ix_ai_interactions_user_id'), 'ai_interactions', ['user_id'], unique=False)
    op.create_table('diagnoses',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('problem_id', sa.Integer(), nullable=False),
    sa.Column('attempt_id', sa.String(length=36), nullable=False),
    sa.Column('assessment_session_id', sa.String(length=36), nullable=True),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('language', sa.String(length=20), nullable=True),
    sa.Column('defect_category', sa.String(length=40), nullable=False),
    sa.Column('root_cause', sa.Text(), nullable=False),
    sa.Column('affected_component', sa.Text(), nullable=False),
    sa.Column('violated_invariant', sa.Text(), nullable=False),
    sa.Column('proposed_correction', sa.Text(), nullable=False),
    sa.Column('reproduction_strategy', sa.Text(), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('deterministic_score', sa.Float(), nullable=True),
    sa.Column('ai_score', sa.Float(), nullable=True),
    sa.Column('evaluation_details', sa.JSON(), nullable=False),
    sa.Column('rubric_version', sa.Integer(), nullable=False),
    sa.Column('evaluator_version', sa.String(length=40), nullable=False),
    sa.Column('ai_status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['attempt_id'], ['challenge_attempts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_diagnoses_assessment_session_id'), 'diagnoses', ['assessment_session_id'], unique=False)
    op.create_index(op.f('ix_diagnoses_attempt_id'), 'diagnoses', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_diagnoses_created_at'), 'diagnoses', ['created_at'], unique=False)
    op.create_index(op.f('ix_diagnoses_problem_id'), 'diagnoses', ['problem_id'], unique=False)
    op.create_index(op.f('ix_diagnoses_user_id'), 'diagnoses', ['user_id'], unique=False)
    op.create_table('fix_explanations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('problem_id', sa.Integer(), nullable=False),
    sa.Column('attempt_id', sa.String(length=36), nullable=False),
    sa.Column('submission_id', sa.String(length=36), nullable=True),
    sa.Column('why_failed', sa.Text(), nullable=False),
    sa.Column('why_works', sa.Text(), nullable=False),
    sa.Column('invariant_preserved', sa.Text(), nullable=False),
    sa.Column('side_effects', sa.Text(), nullable=False),
    sa.Column('additional_tests', sa.Text(), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('deterministic_score', sa.Float(), nullable=True),
    sa.Column('ai_score', sa.Float(), nullable=True),
    sa.Column('evaluation_details', sa.JSON(), nullable=False),
    sa.Column('rubric_version', sa.Integer(), nullable=False),
    sa.Column('evaluator_version', sa.String(length=40), nullable=False),
    sa.Column('ai_status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['attempt_id'], ['challenge_attempts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['problem_id'], ['problems.id'], ),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fix_explanations_attempt_id'), 'fix_explanations', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_fix_explanations_created_at'), 'fix_explanations', ['created_at'], unique=False)
    op.create_index(op.f('ix_fix_explanations_problem_id'), 'fix_explanations', ['problem_id'], unique=False)
    op.create_index(op.f('ix_fix_explanations_user_id'), 'fix_explanations', ['user_id'], unique=False)
    op.create_table('incident_resolutions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('diagnosis_id', sa.String(length=36), nullable=True),
    sa.Column('submission_id', sa.String(length=36), nullable=True),
    sa.Column('impact_assessment', sa.Text(), nullable=False),
    sa.Column('remediation', sa.Text(), nullable=False),
    sa.Column('prevention', sa.Text(), nullable=False),
    sa.Column('regression_tests', sa.JSON(), nullable=False),
    sa.Column('regression_results', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('scores', sa.JSON(), nullable=False),
    sa.Column('rubric_version', sa.Integer(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['diagnosis_id'], ['diagnoses.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['session_id'], ['incident_sessions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incident_resolutions_session_id'), 'incident_resolutions', ['session_id'], unique=False)
    op.create_index(op.f('ix_incident_resolutions_status'), 'incident_resolutions', ['status'], unique=False)
    op.create_index(op.f('ix_incident_resolutions_user_id'), 'incident_resolutions', ['user_id'], unique=False)
    # Existing tables: batch mode keeps SQLite (tests/dev) and PostgreSQL (Compose) compatible.
    # Every new column is nullable or has a server default, so existing rows remain valid.
    with op.batch_alter_table('problems') as batch:
        batch.add_column(sa.Column('visibility', sa.String(length=20), server_default='public', nullable=False))
        batch.add_column(sa.Column('version', sa.Integer(), server_default='1', nullable=False))
        batch.add_column(sa.Column('content_hash', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('diagnosis_mode', sa.String(length=10), server_default='optional', nullable=False))
        batch.add_column(sa.Column('diagnosis_rubric', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('rubric_version', sa.Integer(), server_default='1', nullable=False))
        batch.add_column(sa.Column('taxonomy', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('quality_status', sa.String(length=20), server_default='unvalidated', nullable=False))
        batch.add_column(sa.Column('extra', sa.JSON(), nullable=True))
        batch.create_index(batch.f('ix_problems_visibility'), ['visibility'], unique=False)
    with op.batch_alter_table('submissions') as batch:
        batch.add_column(sa.Column('attempt_id', sa.String(length=36), nullable=True))
        batch.add_column(sa.Column('assessment_session_id', sa.String(length=36), nullable=True))
        batch.add_column(sa.Column('diagnosis_id', sa.String(length=36), nullable=True))
        batch.add_column(sa.Column('diff_stats', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('quality', sa.JSON(), nullable=True))
        batch.create_index(batch.f('ix_submissions_assessment_session_id'), ['assessment_session_id'], unique=False)
        batch.create_index(batch.f('ix_submissions_attempt_id'), ['attempt_id'], unique=False)
        batch.create_foreign_key('fk_submissions_diagnosis_id', 'diagnoses', ['diagnosis_id'], ['id'], ondelete='SET NULL')
        batch.create_foreign_key('fk_submissions_attempt_id', 'challenge_attempts', ['attempt_id'], ['id'], ondelete='SET NULL')
        batch.create_foreign_key('fk_submissions_assessment_session_id', 'assessment_sessions',
                                 ['assessment_session_id'], ['id'], ondelete='CASCADE')
    with op.batch_alter_table('hints') as batch:
        batch.add_column(sa.Column('attempt_id', sa.String(length=36), nullable=True))
        batch.add_column(sa.Column('assessment_session_id', sa.String(length=36), nullable=True))
        batch.add_column(sa.Column('context', sa.JSON(), nullable=True))
        batch.create_index(batch.f('ix_hints_assessment_session_id'), ['assessment_session_id'], unique=False)
        batch.create_index(batch.f('ix_hints_attempt_id'), ['attempt_id'], unique=False)
        batch.create_foreign_key('fk_hints_attempt_id', 'challenge_attempts', ['attempt_id'], ['id'], ondelete='SET NULL')
        batch.create_foreign_key('fk_hints_assessment_session_id', 'assessment_sessions',
                                 ['assessment_session_id'], ['id'], ondelete='CASCADE')
    with op.batch_alter_table('problem_submissions') as batch:
        batch.add_column(sa.Column('problem_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_problem_submissions_problem_id', 'problems', ['problem_id'], ['id'], ondelete='SET NULL')

def downgrade():
    with op.batch_alter_table('problem_submissions') as batch:
        batch.drop_constraint('fk_problem_submissions_problem_id', type_='foreignkey')
        batch.drop_column('problem_id')
    with op.batch_alter_table('hints') as batch:
        batch.drop_constraint('fk_hints_assessment_session_id', type_='foreignkey')
        batch.drop_constraint('fk_hints_attempt_id', type_='foreignkey')
        batch.drop_index(batch.f('ix_hints_attempt_id'))
        batch.drop_index(batch.f('ix_hints_assessment_session_id'))
        batch.drop_column('context')
        batch.drop_column('assessment_session_id')
        batch.drop_column('attempt_id')
    with op.batch_alter_table('submissions') as batch:
        batch.drop_constraint('fk_submissions_assessment_session_id', type_='foreignkey')
        batch.drop_constraint('fk_submissions_attempt_id', type_='foreignkey')
        batch.drop_constraint('fk_submissions_diagnosis_id', type_='foreignkey')
        batch.drop_index(batch.f('ix_submissions_attempt_id'))
        batch.drop_index(batch.f('ix_submissions_assessment_session_id'))
        batch.drop_column('quality')
        batch.drop_column('diff_stats')
        batch.drop_column('diagnosis_id')
        batch.drop_column('assessment_session_id')
        batch.drop_column('attempt_id')
    with op.batch_alter_table('problems') as batch:
        batch.drop_index(batch.f('ix_problems_visibility'))
        batch.drop_column('extra')
        batch.drop_column('quality_status')
        batch.drop_column('taxonomy')
        batch.drop_column('rubric_version')
        batch.drop_column('diagnosis_rubric')
        batch.drop_column('diagnosis_mode')
        batch.drop_column('content_hash')
        batch.drop_column('version')
        batch.drop_column('visibility')
    op.drop_index(op.f('ix_incident_resolutions_user_id'), table_name='incident_resolutions')
    op.drop_index(op.f('ix_incident_resolutions_status'), table_name='incident_resolutions')
    op.drop_index(op.f('ix_incident_resolutions_session_id'), table_name='incident_resolutions')
    op.drop_table('incident_resolutions')
    op.drop_index(op.f('ix_fix_explanations_user_id'), table_name='fix_explanations')
    op.drop_index(op.f('ix_fix_explanations_problem_id'), table_name='fix_explanations')
    op.drop_index(op.f('ix_fix_explanations_created_at'), table_name='fix_explanations')
    op.drop_index(op.f('ix_fix_explanations_attempt_id'), table_name='fix_explanations')
    op.drop_table('fix_explanations')
    op.drop_index(op.f('ix_diagnoses_user_id'), table_name='diagnoses')
    op.drop_index(op.f('ix_diagnoses_problem_id'), table_name='diagnoses')
    op.drop_index(op.f('ix_diagnoses_created_at'), table_name='diagnoses')
    op.drop_index(op.f('ix_diagnoses_attempt_id'), table_name='diagnoses')
    op.drop_index(op.f('ix_diagnoses_assessment_session_id'), table_name='diagnoses')
    op.drop_table('diagnoses')
    op.drop_index(op.f('ix_ai_interactions_user_id'), table_name='ai_interactions')
    op.drop_index(op.f('ix_ai_interactions_status'), table_name='ai_interactions')
    op.drop_index(op.f('ix_ai_interactions_problem_id'), table_name='ai_interactions')
    op.drop_index(op.f('ix_ai_interactions_created_at'), table_name='ai_interactions')
    op.drop_index(op.f('ix_ai_interactions_attempt_id'), table_name='ai_interactions')
    op.drop_index(op.f('ix_ai_interactions_assessment_session_id'), table_name='ai_interactions')
    op.drop_table('ai_interactions')
    op.drop_index(op.f('ix_challenge_attempts_user_id'), table_name='challenge_attempts')
    op.drop_index(op.f('ix_challenge_attempts_status'), table_name='challenge_attempts')
    op.drop_index(op.f('ix_challenge_attempts_problem_id'), table_name='challenge_attempts')
    op.drop_index(op.f('ix_challenge_attempts_incident_session_id'), table_name='challenge_attempts')
    op.drop_index(op.f('ix_challenge_attempts_assessment_session_id'), table_name='challenge_attempts')
    op.drop_table('challenge_attempts')
    op.drop_index(op.f('ix_assessment_sessions_user_id'), table_name='assessment_sessions')
    op.drop_index(op.f('ix_assessment_sessions_status'), table_name='assessment_sessions')
    op.drop_index(op.f('ix_assessment_sessions_expires_at'), table_name='assessment_sessions')
    op.drop_index(op.f('ix_assessment_sessions_assessment_id'), table_name='assessment_sessions')
    op.drop_table('assessment_sessions')
    op.drop_index(op.f('ix_assessment_invitations_email'), table_name='assessment_invitations')
    op.drop_index(op.f('ix_assessment_invitations_assessment_id'), table_name='assessment_invitations')
    op.drop_table('assessment_invitations')
    op.drop_index(op.f('ix_assessments_status'), table_name='assessments')
    op.drop_index(op.f('ix_assessments_slug'), table_name='assessments')
    op.drop_index(op.f('ix_assessments_organization_id'), table_name='assessments')
    op.drop_table('assessments')
    op.drop_index(op.f('ix_organization_members_user_id'), table_name='organization_members')
    op.drop_table('organization_members')
    op.drop_index(op.f('ix_mutation_cases_status'), table_name='mutation_cases')
    op.drop_index(op.f('ix_mutation_cases_run_id'), table_name='mutation_cases')
    op.drop_table('mutation_cases')
    op.drop_index(op.f('ix_incident_sessions_user_id'), table_name='incident_sessions')
    op.drop_index(op.f('ix_incident_sessions_status'), table_name='incident_sessions')
    op.drop_index(op.f('ix_incident_sessions_incident_id'), table_name='incident_sessions')
    op.drop_table('incident_sessions')
    op.drop_index(op.f('ix_competency_profiles_organization_id'), table_name='competency_profiles')
    op.drop_table('competency_profiles')
    op.drop_index(op.f('ix_organizations_slug'), table_name='organizations')
    op.drop_table('organizations')
    op.drop_index(op.f('ix_mutation_runs_status'), table_name='mutation_runs')
    op.drop_index(op.f('ix_mutation_runs_problem_id'), table_name='mutation_runs')
    op.drop_index(op.f('ix_mutation_runs_created_at'), table_name='mutation_runs')
    op.drop_table('mutation_runs')
    op.drop_index(op.f('ix_incidents_status'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_slug'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_category'), table_name='incidents')
    op.drop_table('incidents')
    op.drop_index(op.f('ix_events_user_id'), table_name='events')
    op.drop_index(op.f('ix_events_type'), table_name='events')
    op.drop_index(op.f('ix_events_incident_session_id'), table_name='events')
    op.drop_index(op.f('ix_events_created_at'), table_name='events')
    op.drop_index(op.f('ix_events_attempt_id'), table_name='events')
    op.drop_index(op.f('ix_events_assessment_session_id'), table_name='events')
    op.drop_table('events')
    op.drop_table('quality_gates')
    op.drop_index(op.f('ix_audit_logs_entity_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')

