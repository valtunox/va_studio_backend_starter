"""Add template_type to projects and ecommerce/crm tables.

Revision ID: 001
Revises:
Create Date: 2025-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add template_type to projects
    op.add_column(
        "projects",
        sa.Column("template_type", sa.String(50), nullable=False, server_default="saas"),
    )
    op.create_index("ix_projects_template_type", "projects", ["template_type"], unique=False)

    # E-commerce tables
    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("compare_at_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost_per_item", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("track_inventory", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("featured_image", sa.String(500), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_project_id", "products", ["project_id"], unique=False)
    op.create_index("ix_products_slug", "products", ["slug"], unique=False)
    op.create_index("ix_products_sku", "products", ["sku"], unique=False)

    op.create_table(
        "orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("shipping_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("shipping_address", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("billing_address", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("stripe_payment_id", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_project_id", "orders", ["project_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"], unique=False)

    # CRM tables
    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="new"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assigned_to_id", sa.UUID(), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_project_id", "leads", ["project_id"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("title", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_project_id", "contacts", ["project_id"], unique=False)

    op.create_table(
        "pipelines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("stages", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipelines_project_id", "pipelines", ["project_id"], unique=False)
    op.create_index("ix_pipelines_slug", "pipelines", ["slug"], unique=False)

    op.create_table(
        "deals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("pipeline_id", sa.UUID(), nullable=True),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("assigned_to_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(50), nullable=False, server_default="lead"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deals_project_id", "deals", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_deals_project_id", "deals")
    op.drop_table("deals")
    op.drop_index("ix_pipelines_slug", "pipelines")
    op.drop_index("ix_pipelines_project_id", "pipelines")
    op.drop_table("pipelines")
    op.drop_index("ix_contacts_project_id", "contacts")
    op.drop_table("contacts")
    op.drop_index("ix_leads_project_id", "leads")
    op.drop_table("leads")
    op.drop_index("ix_order_items_product_id", "order_items")
    op.drop_index("ix_order_items_order_id", "order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_project_id", "orders")
    op.drop_table("orders")
    op.drop_index("ix_products_sku", "products")
    op.drop_index("ix_products_slug", "products")
    op.drop_index("ix_products_project_id", "products")
    op.drop_table("products")
    op.drop_index("ix_projects_template_type", "projects")
    op.drop_column("projects", "template_type")
