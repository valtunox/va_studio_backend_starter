"""
Finance Models

Accounts, transactions, budgets, invoices, P&L, cash flow —
scoped by project_id for multi-use-case backend.

Matches the frontend finance template data structures:
  account cards (checking/savings/investment/credit),
  transactions (income/expense/transfer with categories),
  budgets (monthly with spent/allocated),
  invoices (client billing with status),
  financial reports (P&L, cash flow, YoY).
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

class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    LOAN = "loan"


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class TransactionCategory(str, Enum):
    INCOME = "income"
    HOUSING = "housing"
    FOOD = "food"
    GROCERIES = "groceries"
    TRANSPORT = "transport"
    ENTERTAINMENT = "entertainment"
    UTILITIES = "utilities"
    SHOPPING = "shopping"
    HEALTH = "health"
    TRAVEL = "travel"
    TRANSFER = "transfer"
    OTHER = "other"


class FinanceInvoiceStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class BudgetPeriod(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


# ---------------------------------------------------------------------------
# Account — bank/financial account
# ---------------------------------------------------------------------------

class Account(Base, TimestampMixin, SoftDeleteMixin):
    """Financial account (checking, savings, investment, credit card)."""

    __tablename__ = "finance_accounts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(30), default=AccountType.CHECKING.value, nullable=False,
    )
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    institution: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    available_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="account",
        foreign_keys="[Transaction.account_id]", lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class Transaction(Base, TimestampMixin):
    """Financial transaction — income, expense, or transfer."""

    __tablename__ = "finance_transactions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    account_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("finance_accounts.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    date: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    merchant: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    balance_after: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    transaction_type: Mapped[str] = mapped_column(
        String(20), default=TransactionType.EXPENSE.value, nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(50), default=TransactionCategory.OTHER.value, nullable=False,
    )
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Transfer link
    transfer_to_account_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("finance_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    account: Mapped[Optional["Account"]] = relationship(
        "Account", back_populates="transactions",
        foreign_keys=[account_id], lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

class Budget(Base, TimestampMixin):
    """Monthly/periodic budget allocation per category."""

    __tablename__ = "finance_budgets"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    allocated: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    period: Mapped[str] = mapped_column(
        String(20), default=BudgetPeriod.MONTHLY.value, nullable=False,
    )
    period_start: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[str]] = mapped_column(Date, nullable=True)

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


# ---------------------------------------------------------------------------
# Finance Invoice — client billing
# ---------------------------------------------------------------------------

class FinanceInvoice(Base, TimestampMixin, SoftDeleteMixin):
    """Client-facing invoice for billing."""

    __tablename__ = "finance_invoices"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    issued_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    paid_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default=FinanceInvoiceStatus.DRAFT.value, nullable=False,
    )

    line_items: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


# ---------------------------------------------------------------------------
# Financial Report Snapshot — stored P&L, cash flow, ratios
# ---------------------------------------------------------------------------

class FinancialReport(Base, TimestampMixin):
    """Snapshot of financial report data (P&L, cash flow, ratios) for a period."""

    __tablename__ = "financial_reports"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    period_start: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[str]] = mapped_column(Date, nullable=True)

    # P&L fields
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    cogs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    operating_expenses: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    net_income: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    # Cash flow fields
    operating_cash_flow: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    investing_cash_flow: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    financing_cash_flow: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    net_cash_change: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    # Ratios / extras stored as JSON
    expense_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ratios: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    yoy_comparison: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
