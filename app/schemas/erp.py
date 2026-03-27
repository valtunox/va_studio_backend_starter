"""ERP schemas — warehouses, inventory, sales/purchase orders, invoices, departments, employees, suppliers."""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------

class WarehouseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., max_length=50)
    location: Optional[str] = None


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = None


class WarehouseResponse(WarehouseBase):
    id: str
    project_id: str
    capacity_percent: int = 0
    total_items: int = 0
    total_value: Decimal = Decimal("0")
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Inventory Item
# ---------------------------------------------------------------------------

class InventoryItemBase(BaseModel):
    sku: str = Field(..., max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = None
    description: Optional[str] = None
    quantity: int = Field(0, ge=0)
    reorder_level: int = Field(0, ge=0)
    unit_cost: Decimal = Field(Decimal("0"), ge=0)
    warehouse_id: Optional[str] = None


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    sku: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
    reorder_level: Optional[int] = Field(None, ge=0)
    unit_cost: Optional[Decimal] = Field(None, ge=0)
    warehouse_id: Optional[str] = None
    status: Optional[str] = None


class InventoryItemResponse(InventoryItemBase):
    id: str
    project_id: str
    status: str = "in-stock"
    total_value: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    eta_variance: Optional[str] = None
    rating: Optional[float] = None


class SupplierResponse(SupplierBase):
    id: str
    project_id: str
    risk_level: str = "low"
    risk_score: int = 0
    eta_variance: Optional[str] = None
    rating: float = 0.0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sales Order
# ---------------------------------------------------------------------------

class SalesOrderItemCreate(BaseModel):
    name: str = Field(..., max_length=255)
    sku: Optional[str] = None
    quantity: int = Field(..., ge=1)
    unit_price: Decimal = Field(..., ge=0)


class SalesOrderItemResponse(BaseModel):
    id: str
    name: str
    sku: Optional[str] = None
    quantity: int
    unit_price: Decimal
    total: Decimal

    model_config = {"from_attributes": True}


class SalesOrderCreate(BaseModel):
    order_number: str = Field(..., max_length=50)
    customer_name: str = Field(..., max_length=255)
    items: List[SalesOrderItemCreate] = []


class SalesOrderUpdate(BaseModel):
    customer_name: Optional[str] = None
    status: Optional[str] = None
    payment_status: Optional[str] = None


class SalesOrderResponse(BaseModel):
    id: str
    project_id: str
    order_number: str
    customer_name: str
    order_date: Optional[datetime] = None
    item_count: int = 0
    total: Decimal = Decimal("0")
    status: str = "pending"
    payment_status: str = "unpaid"
    items: List[SalesOrderItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------

class PurchaseOrderItemCreate(BaseModel):
    name: str = Field(..., max_length=255)
    sku: Optional[str] = None
    quantity: int = Field(..., ge=1)
    unit_cost: Decimal = Field(..., ge=0)


class PurchaseOrderItemResponse(BaseModel):
    id: str
    name: str
    sku: Optional[str] = None
    quantity: int
    unit_cost: Decimal
    total: Decimal

    model_config = {"from_attributes": True}


class PurchaseOrderCreate(BaseModel):
    po_number: str = Field(..., max_length=50)
    supplier_id: Optional[str] = None
    expected_date: Optional[datetime] = None
    items: List[PurchaseOrderItemCreate] = []


class PurchaseOrderUpdate(BaseModel):
    status: Optional[str] = None
    expected_date: Optional[datetime] = None


class PurchaseOrderResponse(BaseModel):
    id: str
    project_id: str
    supplier_id: Optional[str] = None
    po_number: str
    order_date: Optional[datetime] = None
    expected_date: Optional[datetime] = None
    total: Decimal = Decimal("0")
    status: str = "draft"
    items: List[PurchaseOrderItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ERP Invoice
# ---------------------------------------------------------------------------

class ErpInvoiceCreate(BaseModel):
    invoice_number: str = Field(..., max_length=50)
    customer_name: str = Field(..., max_length=255)
    amount: Decimal = Field(..., ge=0)
    due_date: Optional[datetime] = None
    sales_order_id: Optional[str] = None


class ErpInvoiceUpdate(BaseModel):
    status: Optional[str] = None
    amount_paid: Optional[Decimal] = Field(None, ge=0)
    due_date: Optional[datetime] = None


class ErpInvoiceResponse(BaseModel):
    id: str
    project_id: str
    sales_order_id: Optional[str] = None
    invoice_number: str
    customer_name: str
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    amount: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")
    status: str = "draft"
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------

class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=20)
    manager_name: Optional[str] = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = None
    manager_name: Optional[str] = None
    manager_id: Optional[str] = None
    budget: Optional[Decimal] = None


class DepartmentResponse(DepartmentBase):
    id: str
    project_id: str
    manager_id: Optional[str] = None
    headcount: int = 0
    budget: Decimal = Decimal("0")
    utilization: int = 0
    performance_score: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

class EmployeeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    role: Optional[str] = None
    department_id: Optional[str] = None
    start_date: Optional[date] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = None
    role: Optional[str] = None
    department_id: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[float] = None
    review_date: Optional[date] = None
    salary: Optional[Decimal] = None


class EmployeeResponse(EmployeeBase):
    id: str
    project_id: str
    user_id: Optional[str] = None
    status: str = "active"
    rating: float = 0.0
    review_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
