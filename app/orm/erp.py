"""
ERP Models

Warehouses, inventory, sales orders, purchase orders, invoices,
departments, employees, suppliers —
scoped by project_id for multi-use-case backend.

Matches the frontend ERP template data structures:
  KPIs, inventory (SKU/warehouse/reorder), sales orders, fulfillment pipeline,
  P&L, invoices, AR/AP, departments, employees, suppliers, plant utilization.
"""

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Float,
    Numeric,
    ForeignKey,
    JSON,
    DateTime,
    Date,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.orm.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.orm.project import Project
    from app.orm.user import User


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InventoryStatus(str, Enum):
    IN_STOCK = "in-stock"
    LOW_STOCK = "low-stock"
    OUT_OF_STOCK = "out-of-stock"


class SalesOrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    ORDERED = "ordered"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    PAID = "paid"
    UNPAID = "unpaid"
    PARTIAL = "partial"


class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on-leave"
    TERMINATED = "terminated"


class SupplierRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------

class Warehouse(Base, TimestampMixin):
    """Warehouse / storage location."""

    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    capacity_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    inventory_items: Mapped[List["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="warehouse", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Inventory Item
# ---------------------------------------------------------------------------

class InventoryItem(Base, TimestampMixin, SoftDeleteMixin):
    """Inventory product — with SKU, warehouse, reorder level, unit cost."""

    __tablename__ = "inventory_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    warehouse_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    sku: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=InventoryStatus.IN_STOCK.value, nullable=False,
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    warehouse: Mapped[Optional["Warehouse"]] = relationship(
        "Warehouse", back_populates="inventory_items", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

class Supplier(Base, TimestampMixin, SoftDeleteMixin):
    """Supplier / vendor for procurement."""

    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    risk_level: Mapped[str] = mapped_column(
        String(20), default=SupplierRisk.LOW.value, nullable=False,
    )
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    eta_variance: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


# ---------------------------------------------------------------------------
# Sales Order
# ---------------------------------------------------------------------------

class SalesOrder(Base, TimestampMixin):
    """Sales order — customer-facing order in ERP context."""

    __tablename__ = "sales_orders"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_date: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=SalesOrderStatus.PENDING.value, nullable=False,
    )
    payment_status: Mapped[str] = mapped_column(
        String(20), default=PaymentStatus.UNPAID.value, nullable=False,
    )

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    items: Mapped[List["SalesOrderItem"]] = relationship(
        "SalesOrderItem", back_populates="order", lazy="selectin",
        cascade="all, delete-orphan",
    )


class SalesOrderItem(Base, TimestampMixin):
    """Line item in a sales order."""

    __tablename__ = "sales_order_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    inventory_item_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("inventory_items.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    order: Mapped["SalesOrder"] = relationship("SalesOrder", back_populates="items")


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------

class PurchaseOrder(Base, TimestampMixin):
    """Purchase order — procurement from suppliers."""

    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    supplier_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    order_date: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_date: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=PurchaseOrderStatus.DRAFT.value, nullable=False,
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    supplier: Mapped[Optional["Supplier"]] = relationship("Supplier", lazy="selectin")
    items: Mapped[List["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem", back_populates="order", lazy="selectin",
        cascade="all, delete-orphan",
    )


class PurchaseOrderItem(Base, TimestampMixin):
    """Line item in a purchase order."""

    __tablename__ = "purchase_order_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="items")


# ---------------------------------------------------------------------------
# ERP Invoice
# ---------------------------------------------------------------------------

class ErpInvoice(Base, TimestampMixin):
    """Invoice — accounts receivable document."""

    __tablename__ = "erp_invoices"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    sales_order_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sales_orders.id", ondelete="SET NULL"),
        nullable=True,
    )

    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    invoice_date: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=InvoiceStatus.DRAFT.value, nullable=False,
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------

class Department(Base, TimestampMixin):
    """Department — organizational unit with headcount and budget."""

    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    manager_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manager_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    headcount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    utilization: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    performance_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    employees: Mapped[List["Employee"]] = relationship(
        "Employee", back_populates="department", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

class Employee(Base, TimestampMixin, SoftDeleteMixin):
    """Employee record linked to a department."""

    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    department_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default=EmployeeStatus.ACTIVE.value, nullable=False,
    )
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True)

    salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="employees", lazy="selectin",
    )
