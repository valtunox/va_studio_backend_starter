"""Finance schemas — accounts, transactions, budgets, invoices, reports."""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    account_type: str = "checking"
    account_number: Optional[str] = Field(None, max_length=50)
    institution: Optional[str] = None
    currency: str = "USD"
    icon: Optional[str] = None
    color: Optional[str] = None


class AccountCreate(AccountBase):
    balance: Decimal = Decimal("0")
    credit_limit: Optional[Decimal] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    account_type: Optional[str] = None
    account_number: Optional[str] = None
    institution: Optional[str] = None
    balance: Optional[Decimal] = None
    available_balance: Optional[Decimal] = None
    credit_limit: Optional[Decimal] = None
    is_active: Optional[bool] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class AccountResponse(AccountBase):
    id: str
    project_id: str
    user_id: Optional[str] = None
    balance: Decimal = Decimal("0")
    available_balance: Optional[Decimal] = None
    credit_limit: Optional[Decimal] = None
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class TransactionBase(BaseModel):
    date: date
    description: str = Field(..., min_length=1, max_length=500)
    merchant: Optional[str] = None
    amount: Decimal
    transaction_type: str = "expense"
    category: str = "other"
    is_recurring: bool = False
    account_id: Optional[str] = None
    notes: Optional[str] = None


class TransactionCreate(TransactionBase):
    transfer_to_account_id: Optional[str] = None


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    description: Optional[str] = Field(None, max_length=500)
    merchant: Optional[str] = None
    amount: Optional[Decimal] = None
    transaction_type: Optional[str] = None
    category: Optional[str] = None
    is_recurring: Optional[bool] = None
    account_id: Optional[str] = None
    notes: Optional[str] = None


class TransactionResponse(TransactionBase):
    id: str
    project_id: str
    user_id: Optional[str] = None
    balance_after: Optional[Decimal] = None
    transfer_to_account_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

class BudgetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str
    icon: Optional[str] = None
    color: Optional[str] = None
    allocated: Decimal = Field(Decimal("0"), ge=0)
    period: str = "monthly"
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    allocated: Optional[Decimal] = Field(None, ge=0)
    spent: Optional[Decimal] = Field(None, ge=0)
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class BudgetResponse(BudgetBase):
    id: str
    project_id: str
    user_id: Optional[str] = None
    spent: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Finance Invoice
# ---------------------------------------------------------------------------

class FinanceInvoiceCreate(BaseModel):
    invoice_number: str = Field(..., max_length=50)
    client_name: str = Field(..., max_length=255)
    client_email: Optional[str] = None
    amount: Decimal = Field(..., ge=0)
    currency: str = "USD"
    issued_date: Optional[date] = None
    due_date: Optional[date] = None
    line_items: Optional[list] = None
    notes: Optional[str] = None


class FinanceInvoiceUpdate(BaseModel):
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    amount: Optional[Decimal] = None
    amount_paid: Optional[Decimal] = None
    status: Optional[str] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    line_items: Optional[list] = None
    notes: Optional[str] = None


class FinanceInvoiceResponse(BaseModel):
    id: str
    project_id: str
    user_id: Optional[str] = None
    invoice_number: str
    client_name: str
    client_email: Optional[str] = None
    amount: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")
    currency: str = "USD"
    issued_date: Optional[date] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    status: str = "draft"
    line_items: Optional[list] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Financial Report
# ---------------------------------------------------------------------------

class FinancialReportCreate(BaseModel):
    report_type: str = Field(..., max_length=30)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    revenue: Decimal = Decimal("0")
    cogs: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    operating_expenses: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")
    operating_cash_flow: Decimal = Decimal("0")
    investing_cash_flow: Decimal = Decimal("0")
    financing_cash_flow: Decimal = Decimal("0")
    net_cash_change: Decimal = Decimal("0")
    expense_breakdown: Optional[dict] = None
    ratios: Optional[dict] = None
    yoy_comparison: Optional[dict] = None


class FinancialReportResponse(BaseModel):
    id: str
    project_id: str
    report_type: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    revenue: Decimal = Decimal("0")
    cogs: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    operating_expenses: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")
    operating_cash_flow: Decimal = Decimal("0")
    investing_cash_flow: Decimal = Decimal("0")
    financing_cash_flow: Decimal = Decimal("0")
    net_cash_change: Decimal = Decimal("0")
    expense_breakdown: Optional[dict] = None
    ratios: Optional[dict] = None
    yoy_comparison: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Spending Summary (read-only aggregations)
# ---------------------------------------------------------------------------

class SpendingCategoryResponse(BaseModel):
    name: str
    percent: float
    amount: Decimal
    color: Optional[str] = None


class NetWorthDataPoint(BaseModel):
    label: str
    value: Decimal


class IncomeExpenseDataPoint(BaseModel):
    label: str
    income: Decimal
    expense: Decimal


class CashFlowStatement(BaseModel):
    operating_inflows: Decimal = Decimal("0")
    operating_outflows: Decimal = Decimal("0")
    operating_net: Decimal = Decimal("0")
    investing_inflows: Decimal = Decimal("0")
    investing_outflows: Decimal = Decimal("0")
    investing_net: Decimal = Decimal("0")
    financing_inflows: Decimal = Decimal("0")
    financing_outflows: Decimal = Decimal("0")
    financing_net: Decimal = Decimal("0")
    net_change: Decimal = Decimal("0")


class ProfitLossStatement(BaseModel):
    revenue: Decimal = Decimal("0")
    cogs: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    operating_expenses: Optional[dict] = None
    total_opex: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")


class YoYComparison(BaseModel):
    metric: str
    current: Decimal
    previous: Decimal
    change: float
