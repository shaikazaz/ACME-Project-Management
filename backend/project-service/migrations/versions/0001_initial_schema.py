"""Initial schema: tables, circular dependency guard and reference data.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Runs inside the database, so no code path can create a circular chain. The
# lock stops two simultaneous inserts from forming a circle together.
CYCLE_GUARD = """
CREATE FUNCTION reject_circular_dependency() RETURNS trigger AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(728402);
    IF EXISTS (
        WITH RECURSIVE downstream AS (
            SELECT successor_id FROM deliverable_dependencies
            WHERE predecessor_id = NEW.successor_id
            UNION
            SELECT d.successor_id FROM deliverable_dependencies d
            JOIN downstream ON d.predecessor_id = downstream.successor_id
        )
        SELECT 1 FROM downstream WHERE successor_id = NEW.predecessor_id
    ) THEN
        RAISE EXCEPTION 'This dependency would create a circular chain'
            USING ERRCODE = 'check_violation',
                  CONSTRAINT = 'deliverable_dependencies_no_cycle';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER deliverable_dependencies_no_cycle
BEFORE INSERT ON deliverable_dependencies
FOR EACH ROW EXECUTE FUNCTION reject_circular_dependency();

CREATE FUNCTION reject_dependency_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Delete and recreate the dependency instead of editing it'
        USING ERRCODE = 'check_violation',
              CONSTRAINT = 'deliverable_dependencies_no_update';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER deliverable_dependencies_no_update
BEFORE UPDATE ON deliverable_dependencies
FOR EACH ROW EXECUTE FUNCTION reject_dependency_update();
"""

EXPENSE_CATEGORIES = (
    "Contractors",
    "Equipment",
    "Infrastructure",
    "Other",
    "Software",
    "Training",
    "Travel",
)

APP_SETTINGS = (
    ("budget_warning_percent", 80, "Budget used (%) that triggers a warning"),
    ("schedule_lag_percent", 15, "Progress gap (%) behind plan that is a risk"),
    ("upcoming_deadline_days", 14, "Days ahead that count as an upcoming deadline"),
)


def _insert_reference_data() -> None:
    """Insert the defaults the application needs. This is not demo data."""
    op.bulk_insert(
        sa.table("expense_categories", sa.column("name")),
        [{"name": name} for name in EXPENSE_CATEGORIES],
    )
    op.bulk_insert(
        sa.table(
            "app_settings",
            sa.column("key"),
            sa.column("value"),
            sa.column("description"),
        ),
        [
            {"key": key, "value": value, "description": description}
            for key, value, description in APP_SETTINGS
        ],
    )


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("value", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "value >= 0", name=op.f("ck_app_settings_value_not_negative")
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_settings")),
    )
    op.create_table(
        "departments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(name) <> ''", name=op.f("ck_departments_name_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
    )
    op.create_index(
        "uq_departments_name_lower",
        "departments",
        [sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(name) <> ''", name=op.f("ck_expense_categories_name_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expense_categories")),
        sa.UniqueConstraint("name", name=op.f("uq_expense_categories_name")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("btrim(email) <> ''", name=op.f("ck_users_email_not_blank")),
        sa.CheckConstraint(
            "btrim(full_name) <> ''", name=op.f("ck_users_full_name_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(password_hash) <> ''", name=op.f("ck_users_password_hash_not_blank")
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'project_manager', 'team_member')",
            name=op.f("ck_users_role_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.literal_column("lower(email)")],
        unique=True,
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("manager_id", sa.BigInteger(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("actual_completion_date", sa.Date(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default="Planned", nullable=False
        ),
        sa.Column(
            "priority", sa.String(length=10), server_default="Medium", nullable=False
        ),
        sa.Column(
            "planned_budget",
            sa.Numeric(precision=14, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'Completed') = (actual_completion_date IS NOT NULL)",
            name=op.f("ck_projects_completion_date_matches_status"),
        ),
        sa.CheckConstraint(
            "btrim(code) <> ''", name=op.f("ck_projects_code_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(name) <> ''", name=op.f("ck_projects_name_not_blank")
        ),
        sa.CheckConstraint(
            "priority IN ('Low', 'Medium', 'High', 'Critical')",
            name=op.f("ck_projects_priority_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('Planned', 'Active', 'On Hold', 'Completed', 'Cancelled')",
            name=op.f("ck_projects_status_valid"),
        ),
        sa.CheckConstraint(
            "actual_completion_date >= start_date",
            name=op.f("ck_projects_completed_after_start"),
        ),
        sa.CheckConstraint(
            "end_date >= start_date", name=op.f("ck_projects_dates_in_order")
        ),
        sa.CheckConstraint(
            "planned_budget >= 0", name=op.f("ck_projects_planned_budget_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_projects_department_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["manager_id"],
            ["users.id"],
            name=op.f("fk_projects_manager_id"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(
        op.f("ix_projects_department_id"), "projects", ["department_id"], unique=False
    )
    op.create_index(
        op.f("ix_projects_end_date"), "projects", ["end_date"], unique=False
    )
    op.create_index(
        op.f("ix_projects_manager_id"), "projects", ["manager_id"], unique=False
    )
    op.create_index(op.f("ix_projects_status"), "projects", ["status"], unique=False)
    op.create_index(
        "uq_projects_code_lower",
        "projects",
        [sa.literal_column("lower(code)")],
        unique=True,
    )
    op.create_table(
        "resources",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("employee_code", sa.String(length=30), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=False),
        sa.Column(
            "skills", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "capacity_percent",
            sa.Numeric(precision=5, scale=2),
            server_default="100",
            nullable=False,
        ),
        sa.Column(
            "availability",
            sa.String(length=20),
            server_default="Available",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "availability IN ('Available', 'On Leave', 'Unavailable')",
            name=op.f("ck_resources_availability_valid"),
        ),
        sa.CheckConstraint(
            "btrim(employee_code) <> ''",
            name=op.f("ck_resources_employee_code_not_blank"),
        ),
        sa.CheckConstraint(
            "btrim(full_name) <> ''", name=op.f("ck_resources_full_name_not_blank")
        ),
        sa.CheckConstraint(
            "capacity_percent BETWEEN 0 AND 100",
            name=op.f("ck_resources_capacity_percent_range"),
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_resources_department_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_resources_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resources")),
        sa.UniqueConstraint("employee_code", name=op.f("uq_resources_employee_code")),
        sa.UniqueConstraint("user_id", name=op.f("uq_resources_user_id")),
    )
    op.create_index(
        op.f("ix_resources_department_id"), "resources", ["department_id"], unique=False
    )
    op.create_index(
        "uq_resources_email_lower",
        "resources",
        [sa.literal_column("lower(email)")],
        unique=True,
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_expenses_amount_positive")),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["expense_categories.id"],
            name=op.f("fk_expenses_category_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_expenses_created_by_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_expenses_project_id"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
    )
    op.create_index(
        op.f("ix_expenses_category_id"), "expenses", ["category_id"], unique=False
    )
    op.create_index(
        op.f("ix_expenses_project_id"), "expenses", ["project_id"], unique=False
    )
    op.create_table(
        "milestones",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(name) <> ''", name=op.f("ck_milestones_name_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_milestones_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_milestones")),
        sa.UniqueConstraint(
            "id", "project_id", name=op.f("uq_milestones_id_project_id")
        ),
        sa.UniqueConstraint(
            "project_id", "name", name=op.f("uq_milestones_project_id_name")
        ),
    )
    op.create_table(
        "project_resource_assignments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "project_role", sa.String(length=120), server_default="", nullable=False
        ),
        sa.Column(
            "allocation_percent", sa.Numeric(precision=5, scale=2), nullable=False
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "allocation_percent > 0 AND allocation_percent <= 100",
            name=op.f("ck_project_resource_assignments_allocation_percent_range"),
        ),
        sa.CheckConstraint(
            "end_date >= start_date",
            name=op.f("ck_project_resource_assignments_dates_in_order"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_resource_assignments_project_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name=op.f("fk_project_resource_assignments_resource_id"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_resource_assignments")),
        sa.UniqueConstraint(
            "project_id",
            "resource_id",
            name=op.f("uq_project_resource_assignments_project_id_resource_id"),
        ),
    )
    op.create_index(
        op.f("ix_project_resource_assignments_resource_id"),
        "project_resource_assignments",
        ["resource_id"],
        unique=False,
    )
    op.create_table(
        "deliverables",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("milestone_id", sa.BigInteger(), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default="Not Started", nullable=False
        ),
        sa.Column(
            "priority", sa.String(length=10), server_default="Medium", nullable=False
        ),
        sa.Column(
            "progress_percent",
            sa.Numeric(precision=5, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "estimated_hours",
            sa.Numeric(precision=8, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "actual_hours",
            sa.Numeric(precision=8, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'Completed') = (completion_date IS NOT NULL)",
            name=op.f("ck_deliverables_completion_date_matches_status"),
        ),
        sa.CheckConstraint(
            "btrim(name) <> ''", name=op.f("ck_deliverables_name_not_blank")
        ),
        sa.CheckConstraint(
            "priority IN ('Low', 'Medium', 'High', 'Critical')",
            name=op.f("ck_deliverables_priority_valid"),
        ),
        sa.CheckConstraint(
            "status <> 'Completed' OR progress_percent = 100",
            name=op.f("ck_deliverables_completed_means_full_progress"),
        ),
        sa.CheckConstraint(
            "status IN ('Not Started', 'In Progress', 'Blocked', 'Completed')",
            name=op.f("ck_deliverables_status_valid"),
        ),
        sa.CheckConstraint(
            "actual_hours >= 0", name=op.f("ck_deliverables_actual_hours_not_negative")
        ),
        sa.CheckConstraint(
            "completion_date >= start_date",
            name=op.f("ck_deliverables_completed_after_start"),
        ),
        sa.CheckConstraint(
            "due_date >= start_date", name=op.f("ck_deliverables_dates_in_order")
        ),
        sa.CheckConstraint(
            "estimated_hours >= 0",
            name=op.f("ck_deliverables_estimated_hours_not_negative"),
        ),
        sa.CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name=op.f("ck_deliverables_progress_percent_range"),
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id", "project_id"],
            ["milestones.id", "milestones.project_id"],
            name=op.f("fk_deliverables_milestone_id_project_id"),
            ondelete="SET NULL (milestone_id)",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["resources.id"],
            name=op.f("fk_deliverables_owner_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_deliverables_project_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deliverables")),
        sa.UniqueConstraint(
            "project_id", "name", name=op.f("uq_deliverables_project_id_name")
        ),
    )
    op.create_index(
        op.f("ix_deliverables_due_date"), "deliverables", ["due_date"], unique=False
    )
    op.create_index(
        op.f("ix_deliverables_milestone_id"),
        "deliverables",
        ["milestone_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deliverables_owner_id"), "deliverables", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_deliverables_status"), "deliverables", ["status"], unique=False
    )
    op.create_table(
        "deliverable_dependencies",
        sa.Column("predecessor_id", sa.BigInteger(), nullable=False),
        sa.Column("successor_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "predecessor_id <> successor_id",
            name=op.f("ck_deliverable_dependencies_not_self"),
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id"],
            ["deliverables.id"],
            name=op.f("fk_deliverable_dependencies_predecessor_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["successor_id"],
            ["deliverables.id"],
            name=op.f("fk_deliverable_dependencies_successor_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "predecessor_id", "successor_id", name=op.f("pk_deliverable_dependencies")
        ),
    )
    op.create_index(
        op.f("ix_deliverable_dependencies_successor_id"),
        "deliverable_dependencies",
        ["successor_id"],
        unique=False,
    )
    op.execute(CYCLE_GUARD)
    _insert_reference_data()


def downgrade() -> None:
    """Refuse to undo: it would drop every table and all business data."""
    raise RuntimeError("Migration 0001 cannot be undone: it would delete all data.")
