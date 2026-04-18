"""
Finance Routes

Accounts, transactions, budgets, invoices, financial reports -
user-scoped with project_id as query param.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.auth.dependencies import get_current_active_user
from app.orm.user import User
from app.orm.finance import (
    Account,
    Transaction,
    Budget,
    FinanceInvoice,
    FinancialReport,
)
from app.schemas.finance import (
    AccountCreate,
    AccountUpdate,
    AccountResponse,
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    BudgetCreate,
    BudgetUpdate,
    BudgetResponse,
    FinanceInvoiceCreate,
    FinanceInvoiceUpdate,
    FinanceInvoiceResponse,
    FinancialReportCreate,
    FinancialReportResponse,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/finance", tags=["Finance"])


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@router.get("/accounts", response_model=PaginatedResponse[AccountResponse])
async def list_accounts(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List financial accounts for the current user."""
    skip = (page - 1) * per_page
    query = select(Account).where(
        Account.user_id == current_user.id,
        Account.project_id == project_id,
        Account.is_deleted == False,
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Account.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    data: AccountCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a financial account."""
    account = Account(
        project_id=project_id,
        user_id=current_user.id,
        name=data.name,
        account_type=data.account_type,
        account_number=data.account_number,
        institution=data.institution,
        currency=data.currency,
        balance=data.balance,
        credit_limit=data.credit_limit,
        icon=data.icon,
        color=data.color,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get an account by ID."""
    result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == current_user.id,
            Account.project_id == project_id,
            Account.is_deleted == False,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    data: AccountUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update an account."""
    result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == current_user.id,
            Account.project_id == project_id,
            Account.is_deleted == False,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(account, k, v)
    await db.commit()
    await db.refresh(account)
    return account


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@router.get("/transactions", response_model=PaginatedResponse[TransactionResponse])
async def list_transactions(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    transaction_type: Optional[str] = Query(None, alias="type"),
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    account_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List transactions with optional filters."""
    skip = (page - 1) * per_page
    query = select(Transaction).where(
        Transaction.user_id == current_user.id,
        Transaction.project_id == project_id,
    )
    if transaction_type:
        query = query.where(Transaction.transaction_type == transaction_type)
    if category:
        query = query.where(Transaction.category == category)
    if date_from:
        query = query.where(Transaction.date >= date_from)
    if date_to:
        query = query.where(Transaction.date <= date_to)
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Transaction.date.desc(), Transaction.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    data: TransactionCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a transaction."""
    transaction = Transaction(
        project_id=project_id,
        user_id=current_user.id,
        account_id=data.account_id,
        date=data.date,
        description=data.description,
        merchant=data.merchant,
        amount=data.amount,
        transaction_type=data.transaction_type,
        category=data.category,
        is_recurring=data.is_recurring,
        transfer_to_account_id=data.transfer_to_account_id,
        notes=data.notes,
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a transaction by ID."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
            Transaction.project_id == project_id,
        )
    )
    transaction = result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str,
    data: TransactionUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a transaction."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
            Transaction.project_id == project_id,
        )
    )
    transaction = result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(transaction, k, v)
    await db.commit()
    await db.refresh(transaction)
    return transaction


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a transaction."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
            Transaction.project_id == project_id,
        )
    )
    transaction = result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await db.delete(transaction)
    await db.commit()
    return {"message": "Transaction deleted"}


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

@router.get("/budgets", response_model=PaginatedResponse[BudgetResponse])
async def list_budgets(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List budgets for the current user."""
    skip = (page - 1) * per_page
    query = select(Budget).where(
        Budget.user_id == current_user.id,
        Budget.project_id == project_id,
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Budget.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/budgets",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_budget(
    data: BudgetCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a budget."""
    budget = Budget(
        project_id=project_id,
        user_id=current_user.id,
        name=data.name,
        category=data.category,
        icon=data.icon,
        color=data.color,
        allocated=data.allocated,
        period=data.period,
        period_start=data.period_start,
        period_end=data.period_end,
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


@router.get("/budgets/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a budget by ID."""
    result = await db.execute(
        select(Budget).where(
            Budget.id == budget_id,
            Budget.user_id == current_user.id,
            Budget.project_id == project_id,
        )
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.patch("/budgets/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str,
    data: BudgetUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a budget."""
    result = await db.execute(
        select(Budget).where(
            Budget.id == budget_id,
            Budget.user_id == current_user.id,
            Budget.project_id == project_id,
        )
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(budget, k, v)
    await db.commit()
    await db.refresh(budget)
    return budget


# ---------------------------------------------------------------------------
# Finance Invoices
# ---------------------------------------------------------------------------

@router.get("/invoices", response_model=PaginatedResponse[FinanceInvoiceResponse])
async def list_invoices(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List finance invoices for the current user."""
    skip = (page - 1) * per_page
    query = select(FinanceInvoice).where(
        FinanceInvoice.user_id == current_user.id,
        FinanceInvoice.project_id == project_id,
        FinanceInvoice.is_deleted == False,
    )
    if status_filter:
        query = query.where(FinanceInvoice.status == status_filter)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(FinanceInvoice.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/invoices",
    response_model=FinanceInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    data: FinanceInvoiceCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a finance invoice."""
    invoice = FinanceInvoice(
        project_id=project_id,
        user_id=current_user.id,
        invoice_number=data.invoice_number,
        client_name=data.client_name,
        client_email=data.client_email,
        amount=data.amount,
        currency=data.currency,
        issued_date=data.issued_date,
        due_date=data.due_date,
        line_items=data.line_items,
        notes=data.notes,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.get("/invoices/{invoice_id}", response_model=FinanceInvoiceResponse)
async def get_invoice(
    invoice_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a finance invoice by ID."""
    result = await db.execute(
        select(FinanceInvoice).where(
            FinanceInvoice.id == invoice_id,
            FinanceInvoice.user_id == current_user.id,
            FinanceInvoice.project_id == project_id,
            FinanceInvoice.is_deleted == False,
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.patch("/invoices/{invoice_id}", response_model=FinanceInvoiceResponse)
async def update_invoice(
    invoice_id: str,
    data: FinanceInvoiceUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a finance invoice."""
    result = await db.execute(
        select(FinanceInvoice).where(
            FinanceInvoice.id == invoice_id,
            FinanceInvoice.user_id == current_user.id,
            FinanceInvoice.project_id == project_id,
            FinanceInvoice.is_deleted == False,
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(invoice, k, v)
    await db.commit()
    await db.refresh(invoice)
    return invoice


# ---------------------------------------------------------------------------
# Financial Reports
# ---------------------------------------------------------------------------

@router.get("/reports", response_model=PaginatedResponse[FinancialReportResponse])
async def list_reports(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    report_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List financial reports."""
    skip = (page - 1) * per_page
    query = select(FinancialReport).where(
        FinancialReport.project_id == project_id,
    )
    if report_type:
        query = query.where(FinancialReport.report_type == report_type)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(FinancialReport.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/reports",
    response_model=FinancialReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    data: FinancialReportCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a financial report snapshot."""
    report = FinancialReport(
        project_id=project_id,
        report_type=data.report_type,
        period_start=data.period_start,
        period_end=data.period_end,
        revenue=data.revenue,
        cogs=data.cogs,
        gross_profit=data.gross_profit,
        operating_expenses=data.operating_expenses,
        net_income=data.net_income,
        operating_cash_flow=data.operating_cash_flow,
        investing_cash_flow=data.investing_cash_flow,
        financing_cash_flow=data.financing_cash_flow,
        net_cash_change=data.net_cash_change,
        expense_breakdown=data.expense_breakdown,
        ratios=data.ratios,
        yoy_comparison=data.yoy_comparison,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/reports/{report_id}", response_model=FinancialReportResponse)
async def get_report(
    report_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a financial report by ID."""
    result = await db.execute(
        select(FinancialReport).where(
            FinancialReport.id == report_id,
            FinancialReport.project_id == project_id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
