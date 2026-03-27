"""
ERP Routes

Warehouses, inventory, suppliers, sales orders, purchase orders,
invoices, departments, employees - scoped by project_id.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.orm.erp import (
    Warehouse,
    InventoryItem,
    Supplier,
    SalesOrder,
    SalesOrderItem,
    PurchaseOrder,
    PurchaseOrderItem,
    ErpInvoice,
    Department,
    Employee,
)
from app.orm.project import Project
from app.schemas.erp import (
    WarehouseCreate,
    WarehouseUpdate,
    WarehouseResponse,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
    SalesOrderCreate,
    SalesOrderUpdate,
    SalesOrderResponse,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderResponse,
    ErpInvoiceCreate,
    ErpInvoiceUpdate,
    ErpInvoiceResponse,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
)
from app.schemas.common import PaginatedResponse
from app.auth.project_dependencies import RequireErpProject

router = APIRouter(prefix="/erp", tags=["ERP"])


# ---------------------------------------------------------------------------
# Warehouses
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/warehouses",
    response_model=PaginatedResponse[WarehouseResponse],
)
async def list_warehouses(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """List warehouses for an ERP project."""
    skip = (page - 1) * per_page
    query = select(Warehouse).where(Warehouse.project_id == project_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Warehouse.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/projects/{project_id}/warehouses",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_warehouse(
    project_id: str,
    data: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Create a warehouse."""
    warehouse = Warehouse(
        project_id=project_id,
        name=data.name,
        code=data.code,
        location=data.location,
    )
    db.add(warehouse)
    await db.commit()
    await db.refresh(warehouse)
    return warehouse


@router.get(
    "/projects/{project_id}/warehouses/{warehouse_id}",
    response_model=WarehouseResponse,
)
async def get_warehouse(
    project_id: str,
    warehouse_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Get a warehouse by ID."""
    result = await db.execute(
        select(Warehouse).where(
            Warehouse.id == warehouse_id,
            Warehouse.project_id == project_id,
        )
    )
    warehouse = result.scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse


@router.patch(
    "/projects/{project_id}/warehouses/{warehouse_id}",
    response_model=WarehouseResponse,
)
async def update_warehouse(
    project_id: str,
    warehouse_id: str,
    data: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Update a warehouse."""
    result = await db.execute(
        select(Warehouse).where(
            Warehouse.id == warehouse_id,
            Warehouse.project_id == project_id,
        )
    )
    warehouse = result.scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(warehouse, k, v)
    await db.commit()
    await db.refresh(warehouse)
    return warehouse


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/inventory",
    response_model=PaginatedResponse[InventoryItemResponse],
)
async def list_inventory(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: str = None,
    category: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """List inventory items for an ERP project."""
    skip = (page - 1) * per_page
    query = select(InventoryItem).where(
        InventoryItem.project_id == project_id,
        InventoryItem.is_deleted == False,
    )
    if status_filter:
        query = query.where(InventoryItem.status == status_filter)
    if category:
        query = query.where(InventoryItem.category == category)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(InventoryItem.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/projects/{project_id}/inventory",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory_item(
    project_id: str,
    data: InventoryItemCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Create an inventory item."""
    total_value = data.unit_cost * data.quantity
    item = InventoryItem(
        project_id=project_id,
        sku=data.sku,
        name=data.name,
        category=data.category,
        description=data.description,
        quantity=data.quantity,
        reorder_level=data.reorder_level,
        unit_cost=data.unit_cost,
        total_value=total_value,
        warehouse_id=data.warehouse_id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get(
    "/projects/{project_id}/inventory/{item_id}",
    response_model=InventoryItemResponse,
)
async def get_inventory_item(
    project_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Get an inventory item by ID."""
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.project_id == project_id,
            InventoryItem.is_deleted == False,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item


@router.patch(
    "/projects/{project_id}/inventory/{item_id}",
    response_model=InventoryItemResponse,
)
async def update_inventory_item(
    project_id: str,
    item_id: str,
    data: InventoryItemUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Update an inventory item."""
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.project_id == project_id,
            InventoryItem.is_deleted == False,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/projects/{project_id}/inventory/{item_id}")
async def delete_inventory_item(
    project_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Soft-delete an inventory item."""
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.project_id == project_id,
            InventoryItem.is_deleted == False,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    item.soft_delete()
    await db.commit()
    return {"message": "Inventory item deleted"}


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/suppliers",
    response_model=PaginatedResponse[SupplierResponse],
)
async def list_suppliers(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    category: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """List suppliers for an ERP project."""
    skip = (page - 1) * per_page
    query = select(Supplier).where(
        Supplier.project_id == project_id,
        Supplier.is_deleted == False,
    )
    if category:
        query = query.where(Supplier.category == category)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Supplier.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/projects/{project_id}/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier(
    project_id: str,
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Create a supplier."""
    supplier = Supplier(
        project_id=project_id,
        name=data.name,
        contact_name=data.contact_name,
        email=data.email,
        phone=data.phone,
        address=data.address,
        category=data.category,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.get(
    "/projects/{project_id}/suppliers/{supplier_id}",
    response_model=SupplierResponse,
)
async def get_supplier(
    project_id: str,
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Get a supplier by ID."""
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.project_id == project_id,
            Supplier.is_deleted == False,
        )
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.patch(
    "/projects/{project_id}/suppliers/{supplier_id}",
    response_model=SupplierResponse,
)
async def update_supplier(
    project_id: str,
    supplier_id: str,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Update a supplier."""
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.project_id == project_id,
            Supplier.is_deleted == False,
        )
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(supplier, k, v)
    await db.commit()
    await db.refresh(supplier)
    return supplier


# ---------------------------------------------------------------------------
# Sales Orders
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/sales-orders",
    response_model=PaginatedResponse[SalesOrderResponse],
)
async def list_sales_orders(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """List sales orders for an ERP project."""
    skip = (page - 1) * per_page
    query = select(SalesOrder).where(SalesOrder.project_id == project_id)
    if status_filter:
        query = query.where(SalesOrder.status == status_filter)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(SalesOrder.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/projects/{project_id}/sales-orders",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sales_order(
    project_id: str,
    data: SalesOrderCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Create a sales order with line items."""
    total = Decimal("0")
    items_to_create = []
    for item in data.items:
        line_total = item.unit_price * item.quantity
        total += line_total
        items_to_create.append(
            SalesOrderItem(
                name=item.name,
                sku=item.sku,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=line_total,
            )
        )
    order = SalesOrder(
        project_id=project_id,
        order_number=data.order_number,
        customer_name=data.customer_name,
        item_count=len(items_to_create),
        total=total,
        items=items_to_create,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.get(
    "/projects/{project_id}/sales-orders/{order_id}",
    response_model=SalesOrderResponse,
)
async def get_sales_order(
    project_id: str,
    order_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Get a sales order by ID."""
    result = await db.execute(
        select(SalesOrder).where(
            SalesOrder.id == order_id,
            SalesOrder.project_id == project_id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return order


@router.patch(
    "/projects/{project_id}/sales-orders/{order_id}",
    response_model=SalesOrderResponse,
)
async def update_sales_order(
    project_id: str,
    order_id: str,
    data: SalesOrderUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Update a sales order."""
    result = await db.execute(
        select(SalesOrder).where(
            SalesOrder.id == order_id,
            SalesOrder.project_id == project_id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(order, k, v)
    await db.commit()
    await db.refresh(order)
    return order


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/purchase-orders",
    response_model=PaginatedResponse[PurchaseOrderResponse],
)
async def list_purchase_orders(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """List purchase orders for an ERP project."""
    skip = (page - 1) * per_page
    query = select(PurchaseOrder).where(PurchaseOrder.project_id == project_id)
    if status_filter:
        query = query.where(PurchaseOrder.status == status_filter)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(PurchaseOrder.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/projects/{project_id}/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_order(
    project_id: str,
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Create a purchase order with line items."""
    total = Decimal("0")
    items_to_create = []
    for item in data.items:
        line_total = item.unit_cost * item.quantity
        total += line_total
        items_to_create.append(
            PurchaseOrderItem(
                name=item.name,
                sku=item.sku,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
                total=line_total,
            )
        )
    order = PurchaseOrder(
        project_id=project_id,
        po_number=data.po_number,
        supplier_id=data.supplier_id,
        expected_date=data.expected_date,
        total=total,
        items=items_to_create,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.get(
    "/projects/{project_id}/purchase-orders/{order_id}",
    response_model=PurchaseOrderResponse,
)
async def get_purchase_order(
    project_id: str,
    order_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Get a purchase order by ID."""
    result = await db.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == order_id,
            PurchaseOrder.project_id == project_id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return order


@router.patch(
    "/projects/{project_id}/purchase-orders/{order_id}",
    response_model=PurchaseOrderResponse,
)
async def update_purchase_order(
    project_id: str,
    order_id: str,
    data: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Update a purchase order."""
    result = await db.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == order_id,
            PurchaseOrder.project_id == project_id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(order, k, v)
    await db.commit()
    await db.refresh(order)
    return order


# ---------------------------------------------------------------------------
# ERP Invoices
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/invoices",
    response_model=PaginatedResponse[ErpInvoiceResponse],
)
async def list_invoices(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """List ERP invoices for a project."""
    skip = (page - 1) * per_page
    query = select(ErpInvoice).where(ErpInvoice.project_id == project_id)
    if status_filter:
        query = query.where(ErpInvoice.status == status_filter)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(ErpInvoice.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/projects/{project_id}/invoices",
    response_model=ErpInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    project_id: str,
    data: ErpInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Create an ERP invoice."""
    invoice = ErpInvoice(
        project_id=project_id,
        invoice_number=data.invoice_number,
        customer_name=data.customer_name,
        amount=data.amount,
        due_date=data.due_date,
        sales_order_id=data.sales_order_id,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.get(
    "/projects/{project_id}/invoices/{invoice_id}",
    response_model=ErpInvoiceResponse,
)
async def get_invoice(
    project_id: str,
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Get an ERP invoice by ID."""
    result = await db.execute(
        select(ErpInvoice).where(
            ErpInvoice.id == invoice_id,
            ErpInvoice.project_id == project_id,
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.patch(
    "/projects/{project_id}/invoices/{invoice_id}",
    response_model=ErpInvoiceResponse,
)
async def update_invoice(
    project_id: str,
    invoice_id: str,
    data: ErpInvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Update an ERP invoice."""
    result = await db.execute(
        select(ErpInvoice).where(
            ErpInvoice.id == invoice_id,
            ErpInvoice.project_id == project_id,
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
# Departments
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/departments",
    response_model=PaginatedResponse[DepartmentResponse],
)
async def list_departments(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """List departments for an ERP project."""
    skip = (page - 1) * per_page
    query = select(Department).where(Department.project_id == project_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Department.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/projects/{project_id}/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    project_id: str,
    data: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Create a department."""
    department = Department(
        project_id=project_id,
        name=data.name,
        code=data.code,
        manager_name=data.manager_name,
    )
    db.add(department)
    await db.commit()
    await db.refresh(department)
    return department


@router.get(
    "/projects/{project_id}/departments/{department_id}",
    response_model=DepartmentResponse,
)
async def get_department(
    project_id: str,
    department_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Get a department by ID."""
    result = await db.execute(
        select(Department).where(
            Department.id == department_id,
            Department.project_id == project_id,
        )
    )
    department = result.scalar_one_or_none()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


@router.patch(
    "/projects/{project_id}/departments/{department_id}",
    response_model=DepartmentResponse,
)
async def update_department(
    project_id: str,
    department_id: str,
    data: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Update a department."""
    result = await db.execute(
        select(Department).where(
            Department.id == department_id,
            Department.project_id == project_id,
        )
    )
    department = result.scalar_one_or_none()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(department, k, v)
    await db.commit()
    await db.refresh(department)
    return department


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/employees",
    response_model=PaginatedResponse[EmployeeResponse],
)
async def list_employees(
    project_id: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: str = None,
    department_id: str = None,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """List employees for an ERP project."""
    skip = (page - 1) * per_page
    query = select(Employee).where(
        Employee.project_id == project_id,
        Employee.is_deleted == False,
    )
    if status_filter:
        query = query.where(Employee.status == status_filter)
    if department_id:
        query = query.where(Employee.department_id == department_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Employee.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/projects/{project_id}/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    project_id: str,
    data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Create an employee."""
    employee = Employee(
        project_id=project_id,
        name=data.name,
        email=data.email,
        role=data.role,
        department_id=data.department_id,
        start_date=data.start_date,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


@router.get(
    "/projects/{project_id}/employees/{employee_id}",
    response_model=EmployeeResponse,
)
async def get_employee(
    project_id: str,
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Get an employee by ID."""
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.project_id == project_id,
            Employee.is_deleted == False,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.patch(
    "/projects/{project_id}/employees/{employee_id}",
    response_model=EmployeeResponse,
)
async def update_employee(
    project_id: str,
    employee_id: str,
    data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(RequireErpProject),
):
    """Update an employee."""
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.project_id == project_id,
            Employee.is_deleted == False,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(employee, k, v)
    await db.commit()
    await db.refresh(employee)
    return employee
