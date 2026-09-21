"""add problem submissions"""
import sqlalchemy as sa
from alembic import op

revision = 'b2c8e4f19a23'
down_revision = '4a9ffce07817'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('problem_submissions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('author_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('difficulty', sa.String(length=10), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('language', sa.String(length=20), nullable=False),
        sa.Column('buggy_code', sa.Text(), nullable=False),
        sa.Column('fixed_code', sa.Text(), nullable=False),
        sa.Column('test_cases', sa.JSON(), nullable=False),
        sa.Column('hint', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('admin_notes', sa.Text(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_problem_submissions_author_id'), 'problem_submissions', ['author_id'], unique=False)
    op.create_index(op.f('ix_problem_submissions_status'), 'problem_submissions', ['status'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_problem_submissions_status'), table_name='problem_submissions')
    op.drop_index(op.f('ix_problem_submissions_author_id'), table_name='problem_submissions')
    op.drop_table('problem_submissions')
