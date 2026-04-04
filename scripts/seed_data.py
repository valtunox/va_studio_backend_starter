#!/usr/bin/env python
"""
Seed database with realistic data across ALL domains.

Usage:
    python scripts/seed_data.py

Idempotent — checks if admin user already exists and skips if so.
Uses the sync SQLAlchemy engine from the project. 2
"""

import sys
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.core.db import get_sync_engine, get_sync_session_factory, discover_orm_models
from app.core.security import get_password_hash

# ORM models
from app.orm.user import User
from app.orm.project import Project
from app.orm.ecommerce import (
    ProductCategory, Seller, Product, Order, OrderItem,
)
from app.orm.crm import (
    Pipeline, Contact, Deal, Activity, CrmTask,
)
from app.orm.erp import (
    Warehouse, InventoryItem, Supplier, SalesOrder, SalesOrderItem,
    PurchaseOrder, PurchaseOrderItem, ErpInvoice, Department, Employee,
)
from app.orm.nutrition import (
    DietProfile, Food, Recipe, RecipeIngredient,
    MealPlan, MealPlanEntry, DailyLog, MealLog,
    GroceryList, GroceryItem, WeightEntry,
)
from app.orm.finance import (
    Account, Transaction, Budget, FinanceInvoice, FinancialReport,
)
from app.orm.blog import Category, Tag, Post, post_tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_uid = lambda: str(uuid4())
_now = datetime.now(timezone.utc)
_today = date.today()


def _dt(days_ago: int = 0) -> datetime:
    """Return a timezone-aware datetime *days_ago* days in the past."""
    return _now - timedelta(days=days_ago)


def _d(days_ago: int = 0) -> date:
    """Return a date *days_ago* days in the past."""
    return _today - timedelta(days=days_ago)


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_users(db: Session) -> tuple:
    print("[1/10] Seeding users ...")
    admin = User(
        id=_uid(),
        email="admin@vastudio.com",
        username="admin",
        full_name="Admin User",
        hashed_password=get_password_hash("Admin123!"),
        role="admin",
        is_active=True,
        is_verified=True,
    )
    demo = User(
        id=_uid(),
        email="demo@vastudio.com",
        username="demo",
        full_name="Demo User",
        hashed_password=get_password_hash("Demo123!"),
        role="user",
        is_active=True,
        is_verified=True,
    )
    db.add_all([admin, demo])
    db.flush()
    print(f"  -> Created admin ({admin.id}) and demo ({demo.id})")
    return admin, demo


def seed_projects(db: Session, demo: User) -> dict:
    print("[2/10] Seeding projects ...")
    specs = [
        ("VA Store", "va-store", "ecommerce", "Full-featured e-commerce marketplace"),
        ("Sales CRM", "sales-crm", "crm", "Customer relationship management system"),
        ("Nexus ERP", "nexus-erp", "erp", "Enterprise resource planning suite"),
        ("NutriTrack", "nutritrack", "blog", "Nutrition and diet tracking platform"),
        ("FinanceHub", "financehub", "saas", "Personal finance management dashboard"),
    ]
    projects = {}
    for name, slug, ttype, desc in specs:
        p = Project(
            id=_uid(), name=name, slug=slug, template_type=ttype,
            description=desc, status="active", is_public=True,
            owner_id=demo.id,
        )
        db.add(p)
        projects[slug] = p
    db.flush()
    print(f"  -> Created {len(projects)} projects")
    return projects


# ---- Ecommerce ----------------------------------------------------------

def seed_ecommerce(db: Session, project: Project, demo: User):
    print("[3/10] Seeding ecommerce (VA Store) ...")
    pid = project.id

    # Categories
    cat_specs = [
        ("Electronics", "electronics", "cpu"),
        ("Fashion", "fashion", "shirt"),
        ("Home & Garden", "home-garden", "home"),
        ("Sports", "sports", "fitness"),
        ("Beauty", "beauty", "sparkles"),
        ("Books", "books", "book"),
    ]
    cats = {}
    for i, (name, slug, icon) in enumerate(cat_specs):
        c = ProductCategory(
            id=_uid(), project_id=pid, name=name, slug=slug,
            icon=icon, sort_order=i,
        )
        db.add(c)
        cats[slug] = c
    db.flush()

    # Sellers
    seller_specs = [
        ("TechZone", "techzone", "San Francisco, CA", 4.8, 150, 4200, True),
        ("FashionHub", "fashionhub", "New York, NY", 4.6, 90, 2800, True),
        ("HomeStyle", "homestyle", "Austin, TX", 4.5, 65, 1500, False),
    ]
    sellers = {}
    for name, slug, loc, rating, prods, sales, verified in seller_specs:
        s = Seller(
            id=_uid(), project_id=pid, name=name, slug=slug,
            location=loc, rating=rating, total_products=prods,
            total_sales=sales, is_verified=verified,
        )
        db.add(s)
        sellers[slug] = s
    db.flush()

    # Products (12)
    img = "https://images.unsplash.com/photo-"
    product_specs = [
        ("MacBook Pro 16\"", "macbook-pro-16", cats["electronics"], sellers["techzone"],
         Decimal("2499.99"), Decimal("2799.99"), 4.9, 342, 1200, True, f"{img}1517336714731-489689fd1ca8?w=400"),
        ("iPhone 15 Pro", "iphone-15-pro", cats["electronics"], sellers["techzone"],
         Decimal("1199.99"), None, 4.8, 567, 3400, False, f"{img}1592750475338-74b7b21085ab?w=400"),
        ("Sony WH-1000XM5", "sony-wh1000xm5", cats["electronics"], sellers["techzone"],
         Decimal("349.99"), Decimal("399.99"), 4.7, 890, 5600, True, f"{img}1505740420928-5e560c06d30e?w=400"),
        ("Nike Air Max 270", "nike-air-max-270", cats["sports"], sellers["fashionhub"],
         Decimal("159.99"), None, 4.5, 234, 890, False, f"{img}1542291026616-b53d1d81fa5c?w=400"),
        ("Levi's 501 Jeans", "levis-501-jeans", cats["fashion"], sellers["fashionhub"],
         Decimal("79.99"), Decimal("98.00"), 4.4, 178, 670, False, f"{img}1541099649105-f69ad21f3246?w=400"),
        ("Cashmere Sweater", "cashmere-sweater", cats["fashion"], sellers["fashionhub"],
         Decimal("189.99"), None, 4.6, 95, 320, False, f"{img}1434389677669-e08b4cac3105?w=400"),
        ("Dyson V15 Vacuum", "dyson-v15-vacuum", cats["home-garden"], sellers["homestyle"],
         Decimal("749.99"), Decimal("799.99"), 4.8, 412, 1890, True, f"{img}1558618666-fcd25c85f82e?w=400"),
        ("KitchenAid Mixer", "kitchenaid-mixer", cats["home-garden"], sellers["homestyle"],
         Decimal("379.99"), None, 4.7, 623, 2100, False, f"{img}1594631252845-29fc4cc8cde9?w=400"),
        ("Yoga Mat Premium", "yoga-mat-premium", cats["sports"], sellers["homestyle"],
         Decimal("49.99"), Decimal("69.99"), 4.3, 156, 980, False, f"{img}1544367567738-a3b0e5e6cb00?w=400"),
        ("La Mer Moisturizer", "la-mer-moisturizer", cats["beauty"], sellers["fashionhub"],
         Decimal("195.00"), None, 4.9, 88, 410, False, f"{img}1571781926291-c477ebfd024b?w=400"),
        ("Atomic Habits", "atomic-habits", cats["books"], sellers["techzone"],
         Decimal("16.99"), Decimal("24.99"), 4.9, 1245, 8900, False, f"{img}1544947950-fa07a98d237f?w=400"),
        ("Samsung 4K Monitor", "samsung-4k-monitor", cats["electronics"], sellers["techzone"],
         Decimal("599.99"), Decimal("699.99"), 4.6, 278, 1340, True, f"{img}1527443224154-c4a3942d3acf?w=400"),
    ]

    products = []
    for (name, slug, cat, seller, price, compare, rating, reviews, sold,
         flash, image) in product_specs:
        discount = None
        if compare:
            discount = int(((compare - price) / compare) * 100)
        p = Product(
            id=_uid(), project_id=pid, category_id=cat.id, seller_id=seller.id,
            name=name, slug=slug, price=price, compare_at_price=compare,
            discount_percent=discount, rating=rating, reviews_count=reviews,
            sold_count=sold, status="active", quantity=500,
            track_inventory=True, free_shipping=(price > Decimal("100")),
            featured_image=image, is_flash_deal=flash,
            flash_deal_end=_dt(-3) if flash else None,
        )
        db.add(p)
        products.append(p)
    db.flush()

    # Orders (5)
    statuses = ["delivered", "shipped", "processing", "pending", "paid"]
    for i in range(5):
        items_count = (i % 3) + 1
        chosen = products[i * 2: i * 2 + items_count + 1] or products[:2]
        subtotal = sum(p.price * 1 for p in chosen)
        tax = (subtotal * Decimal("0.08")).quantize(Decimal("0.01"))
        total = subtotal + tax

        order = Order(
            id=_uid(), project_id=pid, user_id=demo.id,
            order_number=f"ORD-{1001 + i}",
            status=statuses[i],
            payment_status="paid" if i < 3 else "unpaid",
            subtotal=subtotal, tax_amount=tax,
            shipping_amount=Decimal("0.00"), discount_amount=Decimal("0.00"),
            total=total,
            customer_email=demo.email, customer_name=demo.full_name,
            shipping_address={"street": "123 Main St", "city": "San Francisco", "state": "CA", "zip": "94102"},
        )
        db.add(order)
        db.flush()

        for prod in chosen:
            oi = OrderItem(
                id=_uid(), order_id=order.id, product_id=prod.id,
                quantity=1, unit_price=prod.price, total=prod.price,
            )
            db.add(oi)
    db.flush()
    print("  -> 6 categories, 3 sellers, 12 products, 5 orders")


# ---- CRM ----------------------------------------------------------------

def seed_crm(db: Session, project: Project, demo: User):
    print("[4/10] Seeding CRM (Sales CRM) ...")
    pid = project.id

    # Pipeline
    pipeline = Pipeline(
        id=_uid(), project_id=pid, name="Sales Pipeline", slug="sales-pipeline",
        stages=["lead", "qualified", "proposal", "negotiation", "won", "lost"],
    )
    db.add(pipeline)
    db.flush()

    # Contacts (8)
    contact_specs = [
        ("Sarah Chen", "sarah.chen@acmecorp.com", "+1-415-555-0101", "Acme Corp", "VP Engineering", "customer", Decimal("125000")),
        ("James Wilson", "james.w@globex.io", "+1-312-555-0102", "Globex Inc", "CTO", "customer", Decimal("89000")),
        ("Maria Garcia", "maria@techstart.co", "+1-628-555-0103", "TechStart", "CEO", "lead", Decimal("45000")),
        ("David Kim", "david.kim@innovate.dev", "+1-510-555-0104", "InnovateDev", "Head of Product", "prospect", Decimal("67000")),
        ("Emily Brown", "emily.b@nexgen.ai", "+1-408-555-0105", "NexGen AI", "Director of Ops", "partner", Decimal("210000")),
        ("Michael Lee", "michael@cloudnine.io", "+1-650-555-0106", "CloudNine", "Founder", "lead", Decimal("32000")),
        ("Jessica Taylor", "jess@rapidscale.com", "+1-213-555-0107", "RapidScale", "Sales Director", "prospect", Decimal("78000")),
        ("Robert Martinez", "robert.m@blueshift.co", "+1-718-555-0108", "BlueShift", "CFO", "customer", Decimal("156000")),
    ]
    contacts = []
    for name, email, phone, company, title, status, value in contact_specs:
        c = Contact(
            id=_uid(), project_id=pid, name=name, email=email, phone=phone,
            company=company, title=title, status=status, value=value,
            last_contact_at=_dt(len(contacts) * 2),
        )
        db.add(c)
        contacts.append(c)
    db.flush()

    # Deals (10)
    deal_specs = [
        ("Acme Enterprise License", "Acme Corp", "won", Decimal("125000"), 100, 45),
        ("Globex Platform Migration", "Globex Inc", "negotiation", Decimal("89000"), 75, 12),
        ("TechStart Pilot Program", "TechStart", "proposal", Decimal("45000"), 50, 8),
        ("InnovateDev Integration", "InnovateDev", "qualified", Decimal("67000"), 35, 5),
        ("NexGen AI Partnership", "NexGen AI", "won", Decimal("210000"), 100, 60),
        ("CloudNine Starter Plan", "CloudNine", "lead", Decimal("32000"), 15, 2),
        ("RapidScale Growth Deal", "RapidScale", "proposal", Decimal("78000"), 55, 10),
        ("BlueShift Data Suite", "BlueShift", "negotiation", Decimal("156000"), 70, 18),
        ("Acme Add-on Modules", "Acme Corp", "qualified", Decimal("35000"), 40, 3),
        ("TechStart Full Rollout", "TechStart", "lost", Decimal("120000"), 0, 30),
    ]
    for i, (name, company, stage, value, prob, days) in enumerate(deal_specs):
        contact = contacts[i % len(contacts)]
        d = Deal(
            id=_uid(), project_id=pid, pipeline_id=pipeline.id,
            contact_id=contact.id, assigned_to_id=demo.id,
            name=name, company=company, stage=stage, value=value,
            probability=prob, days_in_stage=days,
            expected_close_date=_dt(-30 + i * 5),
            loss_reason="Budget constraints" if stage == "lost" else None,
        )
        db.add(d)
    db.flush()

    # Activities (6)
    activity_specs = [
        ("call", "Discovery call with Sarah Chen at Acme Corp"),
        ("email", "Sent proposal document to Globex Inc"),
        ("meeting", "Product demo with TechStart team"),
        ("note", "Follow-up needed for InnovateDev integration timeline"),
        ("call", "Quarterly review call with NexGen AI"),
        ("email", "Contract renewal reminder sent to BlueShift"),
    ]
    for i, (atype, desc) in enumerate(activity_specs):
        a = Activity(
            id=_uid(), project_id=pid, user_id=demo.id,
            type=atype, description=desc,
            related_type="contact", related_id=contacts[i].id,
        )
        db.add(a)
    db.flush()

    # CRM Tasks (5)
    task_specs = [
        ("Follow up with Acme Corp on license expansion", "high", 3, False),
        ("Prepare demo environment for TechStart", "urgent", 1, False),
        ("Send updated pricing to Globex", "medium", 5, False),
        ("Review BlueShift contract terms", "high", 2, False),
        ("Update CRM records for Q1 pipeline", "low", 7, True),
    ]
    for title, priority, due_days, done in task_specs:
        t = CrmTask(
            id=_uid(), project_id=pid,
            title=title, priority=priority, is_done=done,
            due_date=_dt(-due_days),
            assigned_to_id=demo.id,
            assignee_name=demo.full_name,
            completed_at=_dt(0) if done else None,
        )
        db.add(t)
    db.flush()
    print("  -> 1 pipeline, 8 contacts, 10 deals, 6 activities, 5 tasks")


# ---- ERP ----------------------------------------------------------------

def seed_erp(db: Session, project: Project, demo: User):
    print("[5/10] Seeding ERP (Nexus ERP) ...")
    pid = project.id

    # Warehouses (3)
    wh_specs = [
        ("WH-Alpha", "WH-A", "San Francisco, CA", 72, 3400, Decimal("1250000")),
        ("WH-Beta", "WH-B", "Chicago, IL", 58, 2100, Decimal("890000")),
        ("WH-Gamma", "WH-G", "Newark, NJ", 85, 4200, Decimal("1780000")),
    ]
    warehouses = []
    for name, code, loc, cap, items, value in wh_specs:
        w = Warehouse(
            id=_uid(), project_id=pid, name=name, code=code,
            location=loc, capacity_percent=cap, total_items=items,
            total_value=value,
        )
        db.add(w)
        warehouses.append(w)
    db.flush()

    # Inventory Items (10)
    inv_specs = [
        ("SKU-EL-001", "Circuit Board Assembly", "Electronics", 450, 100, Decimal("24.50"), warehouses[0]),
        ("SKU-EL-002", "LED Display Panel", "Electronics", 280, 50, Decimal("89.00"), warehouses[0]),
        ("SKU-MC-001", "Steel Bracket Set", "Mechanical", 1200, 200, Decimal("8.75"), warehouses[1]),
        ("SKU-MC-002", "Hydraulic Pump Unit", "Mechanical", 35, 20, Decimal("345.00"), warehouses[1]),
        ("SKU-PK-001", "Corrugated Shipping Box", "Packaging", 5000, 1000, Decimal("1.25"), warehouses[2]),
        ("SKU-PK-002", "Bubble Wrap Roll 100m", "Packaging", 120, 30, Decimal("18.50"), warehouses[2]),
        ("SKU-EL-003", "Power Supply Module", "Electronics", 85, 40, Decimal("56.00"), warehouses[0]),
        ("SKU-CH-001", "Industrial Adhesive 5L", "Chemicals", 200, 50, Decimal("32.00"), warehouses[1]),
        ("SKU-MC-003", "Aluminum Heat Sink", "Mechanical", 650, 150, Decimal("12.80"), warehouses[2]),
        ("SKU-EL-004", "USB-C Connector Pack", "Electronics", 3000, 500, Decimal("3.20"), warehouses[0]),
    ]
    inv_items = []
    for sku, name, cat, qty, reorder, cost, wh in inv_specs:
        status = "in-stock"
        if qty <= reorder:
            status = "low-stock"
        if qty == 0:
            status = "out-of-stock"
        item = InventoryItem(
            id=_uid(), project_id=pid, warehouse_id=wh.id,
            sku=sku, name=name, category=cat, quantity=qty,
            reorder_level=reorder, unit_cost=cost,
            total_value=(cost * qty).quantize(Decimal("0.01")),
            status=status,
        )
        db.add(item)
        inv_items.append(item)
    db.flush()

    # Suppliers (3)
    supplier_specs = [
        ("Shenzhen MicroParts Ltd", "Wei Zhang", "wei@microparts.cn", "+86-755-8888-0001", "Electronics", "low", 15, "+1.2 days", 4.7),
        ("MidWest Steel Corp", "Tom Baker", "tom@midweststeel.com", "+1-312-555-0201", "Mechanical", "medium", 42, "+3.5 days", 3.9),
        ("PackRight Solutions", "Anna Novak", "anna@packright.eu", "+49-30-5555-0301", "Packaging", "high", 68, "+5.1 days", 3.2),
    ]
    suppliers = []
    for name, contact, email, phone, cat, risk, score, eta, rating in supplier_specs:
        s = Supplier(
            id=_uid(), project_id=pid, name=name, contact_name=contact,
            email=email, phone=phone, category=cat,
            risk_level=risk, risk_score=score, eta_variance=eta, rating=rating,
        )
        db.add(s)
        suppliers.append(s)
    db.flush()

    # Sales Orders (5)
    so_specs = [
        ("SO-2024-001", "Acme Corp", "delivered", "paid", 3, Decimal("12450.00")),
        ("SO-2024-002", "Globex Inc", "shipped", "paid", 5, Decimal("8900.00")),
        ("SO-2024-003", "TechStart", "processing", "partial", 2, Decimal("5670.00")),
        ("SO-2024-004", "InnovateDev", "pending", "unpaid", 4, Decimal("15200.00")),
        ("SO-2024-005", "NexGen AI", "delivered", "paid", 6, Decimal("22300.00")),
    ]
    sales_orders = []
    for order_num, cust, status, pay, items, total in so_specs:
        so = SalesOrder(
            id=_uid(), project_id=pid, order_number=order_num,
            customer_name=cust, order_date=_dt(len(sales_orders) * 5),
            item_count=items, total=total, status=status, payment_status=pay,
        )
        db.add(so)
        sales_orders.append(so)
    db.flush()

    # Sales Order Items (a couple per order)
    for so in sales_orders:
        for j in range(2):
            inv = inv_items[(sales_orders.index(so) * 2 + j) % len(inv_items)]
            qty = (j + 1) * 10
            unit_price = inv.unit_cost * Decimal("1.4")
            soi = SalesOrderItem(
                id=_uid(), order_id=so.id, inventory_item_id=inv.id,
                name=inv.name, sku=inv.sku, quantity=qty,
                unit_price=unit_price.quantize(Decimal("0.01")),
                total=(unit_price * qty).quantize(Decimal("0.01")),
            )
            db.add(soi)
    db.flush()

    # Purchase Orders (3)
    po_specs = [
        ("PO-2024-001", suppliers[0], "received", Decimal("18500.00")),
        ("PO-2024-002", suppliers[1], "ordered", Decimal("7200.00")),
        ("PO-2024-003", suppliers[2], "approved", Decimal("3400.00")),
    ]
    purchase_orders = []
    for po_num, supplier, status, total in po_specs:
        po = PurchaseOrder(
            id=_uid(), project_id=pid, supplier_id=supplier.id,
            po_number=po_num, order_date=_dt(20 + len(purchase_orders) * 7),
            expected_date=_dt(5 + len(purchase_orders) * 3),
            total=total, status=status,
        )
        db.add(po)
        purchase_orders.append(po)
    db.flush()

    # Purchase Order Items
    for po in purchase_orders:
        inv = inv_items[purchase_orders.index(po) * 3 % len(inv_items)]
        qty = 200
        poi = PurchaseOrderItem(
            id=_uid(), order_id=po.id,
            name=inv.name, sku=inv.sku, quantity=qty,
            unit_cost=inv.unit_cost,
            total=(inv.unit_cost * qty).quantize(Decimal("0.01")),
        )
        db.add(poi)
    db.flush()

    # ERP Invoices (4)
    inv_specs_erp = [
        ("INV-2024-001", "Acme Corp", "paid", Decimal("12450.00"), Decimal("12450.00")),
        ("INV-2024-002", "Globex Inc", "sent", Decimal("8900.00"), Decimal("0.00")),
        ("INV-2024-003", "TechStart", "overdue", Decimal("5670.00"), Decimal("2000.00")),
        ("INV-2024-004", "NexGen AI", "paid", Decimal("22300.00"), Decimal("22300.00")),
    ]
    for i, (inv_num, cust, status, amount, paid) in enumerate(inv_specs_erp):
        so_ref = sales_orders[i] if i < len(sales_orders) else None
        einv = ErpInvoice(
            id=_uid(), project_id=pid,
            sales_order_id=so_ref.id if so_ref else None,
            invoice_number=inv_num, customer_name=cust,
            invoice_date=_dt(30 - i * 5), due_date=_dt(-(i * 5)),
            amount=amount, amount_paid=paid, status=status,
        )
        db.add(einv)
    db.flush()

    # Departments (4)
    dept_specs = [
        ("Manufacturing", "MFG", "John Harris", 45, Decimal("2200000"), 82, 88),
        ("Engineering", "ENG", "Lisa Park", 32, Decimal("3500000"), 91, 94),
        ("Sales", "SLS", "Mark Thompson", 18, Decimal("1200000"), 76, 85),
        ("Operations", "OPS", "Diana Cruz", 25, Decimal("1800000"), 88, 90),
    ]
    departments = []
    for name, code, mgr, hc, budget, util, perf in dept_specs:
        d = Department(
            id=_uid(), project_id=pid, name=name, code=code,
            manager_name=mgr, headcount=hc, budget=budget,
            utilization=util, performance_score=perf,
        )
        db.add(d)
        departments.append(d)
    db.flush()

    # Employees (8)
    emp_specs = [
        ("John Harris", "john.harris@nexuserp.com", "Plant Manager", departments[0], Decimal("120000"), 4.5, _d(365)),
        ("Lisa Park", "lisa.park@nexuserp.com", "VP Engineering", departments[1], Decimal("155000"), 4.8, _d(180)),
        ("Carlos Ruiz", "carlos.r@nexuserp.com", "Mechanical Engineer", departments[1], Decimal("95000"), 4.2, _d(90)),
        ("Aya Tanaka", "aya.t@nexuserp.com", "QA Lead", departments[0], Decimal("88000"), 4.0, _d(60)),
        ("Mark Thompson", "mark.t@nexuserp.com", "Sales Director", departments[2], Decimal("130000"), 4.6, _d(120)),
        ("Priya Sharma", "priya.s@nexuserp.com", "Account Executive", departments[2], Decimal("75000"), 3.9, _d(45)),
        ("Diana Cruz", "diana.c@nexuserp.com", "Operations Manager", departments[3], Decimal("110000"), 4.4, _d(200)),
        ("Jake Olsen", "jake.o@nexuserp.com", "Logistics Coordinator", departments[3], Decimal("68000"), 3.7, _d(30)),
    ]
    for name, email, role, dept, salary, rating, review in emp_specs:
        e = Employee(
            id=_uid(), project_id=pid, department_id=dept.id,
            name=name, email=email, role=role,
            start_date=_d(365 + emp_specs.index((name, email, role, dept, salary, rating, review)) * 60),
            status="active", salary=salary, rating=rating, review_date=review,
        )
        db.add(e)
    db.flush()
    print("  -> 3 warehouses, 10 inventory, 3 suppliers, 5 SO, 3 PO, 4 invoices, 4 depts, 8 employees")


# ---- Nutrition -----------------------------------------------------------

def seed_nutrition(db: Session, project: Project, demo: User):
    print("[6/10] Seeding nutrition (NutriTrack) ...")
    pid = project.id
    uid = demo.id

    # Diet Profile
    dp = DietProfile(
        id=_uid(), project_id=pid, user_id=uid,
        diet_type="balanced", goal="maintenance",
        calorie_target=2200, protein_target=150, carbs_target=260,
        fat_target=75, fiber_target=32, water_target=8,
        current_weight=182.0, target_weight=175.0, height=71.0,
        restrictions=["gluten-free"], allergies=["shellfish"],
    )
    db.add(dp)

    # Foods (15)
    food_specs = [
        ("Chicken Breast (grilled)", None, "Protein", "6 oz", "oz", 280, 52.0, 0.0, 6.0, 0.0, 0.0, 120.0),
        ("Brown Rice (cooked)", None, "Grains", "1 cup", "cup", 215, 5.0, 45.0, 1.8, 3.5, 0.7, 10.0),
        ("Broccoli (steamed)", None, "Vegetables", "1 cup", "cup", 55, 3.7, 11.0, 0.6, 5.1, 2.2, 64.0),
        ("Salmon Fillet", None, "Protein", "6 oz", "oz", 350, 38.0, 0.0, 21.0, 0.0, 0.0, 75.0),
        ("Sweet Potato (baked)", None, "Vegetables", "1 medium", "each", 103, 2.3, 24.0, 0.1, 3.8, 7.4, 41.0),
        ("Greek Yogurt (plain)", "Fage", "Dairy", "1 cup", "cup", 130, 22.0, 8.0, 0.7, 0.0, 7.0, 80.0),
        ("Almonds (raw)", None, "Nuts", "1 oz", "oz", 164, 6.0, 6.0, 14.0, 3.5, 1.2, 0.3),
        ("Banana", None, "Fruits", "1 medium", "each", 105, 1.3, 27.0, 0.4, 3.1, 14.4, 1.2),
        ("Eggs (whole, scrambled)", None, "Protein", "2 large", "each", 182, 12.0, 2.0, 14.0, 0.0, 1.0, 320.0),
        ("Spinach (raw)", None, "Vegetables", "2 cups", "cup", 14, 1.7, 2.2, 0.2, 1.3, 0.3, 48.0),
        ("Quinoa (cooked)", None, "Grains", "1 cup", "cup", 222, 8.0, 39.0, 3.6, 5.2, 1.6, 13.0),
        ("Avocado", None, "Fruits", "1/2 medium", "each", 120, 1.5, 6.0, 11.0, 5.0, 0.5, 5.5),
        ("Oats (rolled, dry)", None, "Grains", "1/2 cup", "cup", 150, 5.0, 27.0, 3.0, 4.0, 0.6, 1.2),
        ("Tuna (canned, in water)", None, "Protein", "5 oz", "oz", 140, 32.0, 0.0, 1.0, 0.0, 0.0, 320.0),
        ("Blueberries (fresh)", None, "Fruits", "1 cup", "cup", 84, 1.1, 21.0, 0.5, 3.6, 15.0, 1.5),
    ]
    foods = []
    for (name, brand, cat, serv_size, serv_unit, cal, prot, carbs, fat,
         fiber, sugar, sodium) in food_specs:
        f = Food(
            id=_uid(), project_id=pid, name=name, brand=brand,
            category=cat, serving_size=serv_size, serving_unit=serv_unit,
            calories=cal, protein=prot, carbs=carbs, fat=fat,
            fiber=fiber, sugar=sugar, sodium=sodium,
        )
        db.add(f)
        foods.append(f)
    db.flush()

    # Recipes (6)
    recipe_specs = [
        ("Grilled Chicken Salad", "A fresh salad with grilled chicken breast, mixed greens, and vinaigrette",
         "Salad", 10, 15, 2, "easy", 380, 42.0, 12.0, 18.0, 4.8, True,
         ["Season chicken with salt, pepper, and olive oil", "Grill chicken 6 min per side", "Toss greens with dressing", "Slice chicken and arrange on salad"]),
        ("Overnight Oats", "Creamy overnight oats with Greek yogurt, banana, and blueberries",
         "Breakfast", 10, 0, 1, "easy", 420, 28.0, 62.0, 10.0, 4.5, True,
         ["Mix oats, yogurt, and milk in a jar", "Add sliced banana and blueberries", "Refrigerate overnight", "Top with almonds before serving"]),
        ("Salmon with Sweet Potato", "Pan-seared salmon with roasted sweet potato and steamed broccoli",
         "Dinner", 15, 25, 2, "medium", 520, 42.0, 35.0, 22.0, 4.6, False,
         ["Season salmon with lemon and dill", "Cube and roast sweet potato at 400F for 20 min", "Pan-sear salmon 4 min per side", "Steam broccoli until tender"]),
        ("Protein Power Bowl", "Brown rice bowl with chicken, avocado, and spinach",
         "Lunch", 10, 20, 1, "easy", 580, 48.0, 52.0, 18.0, 4.3, False,
         ["Cook brown rice according to package", "Grill chicken and slice", "Assemble bowl with rice, chicken, avocado, spinach", "Drizzle with soy-ginger dressing"]),
        ("Quinoa Veggie Stir-Fry", "Colorful stir-fry with quinoa, broccoli, and almonds",
         "Lunch", 10, 15, 2, "easy", 340, 14.0, 48.0, 12.0, 4.1, False,
         ["Cook quinoa and set aside", "Stir-fry broccoli and spinach in olive oil", "Add cooked quinoa and toss", "Top with crushed almonds"]),
        ("Tuna Avocado Wrap", "High-protein wrap with tuna, avocado, and fresh veggies",
         "Lunch", 10, 0, 1, "easy", 410, 36.0, 28.0, 18.0, 4.4, False,
         ["Mix tuna with lemon juice and pepper", "Mash avocado and spread on wrap", "Add tuna mixture and spinach", "Roll tightly and slice in half"]),
    ]
    recipes = []
    for (title, desc, cat, prep, cook, servings, diff, cal, prot, carbs, fat,
         rating, featured, instructions) in recipe_specs:
        r = Recipe(
            id=_uid(), project_id=pid, user_id=uid,
            title=title, description=desc, category=cat,
            prep_time=prep, cook_time=cook, servings=servings,
            difficulty=diff, calories=cal, protein=prot, carbs=carbs,
            fat=fat, rating=rating, is_featured=featured,
            instructions=instructions,
        )
        db.add(r)
        recipes.append(r)
    db.flush()

    # Recipe Ingredients (some for each recipe)
    ingredient_map = {
        0: [(foods[0], 1.0, "serving"), (foods[9], 2.0, "cup"), (foods[11], 0.5, "each")],  # Chicken Salad
        1: [(foods[12], 0.5, "cup"), (foods[5], 1.0, "cup"), (foods[7], 1.0, "each"), (foods[14], 0.5, "cup")],  # Overnight Oats
        2: [(foods[3], 1.0, "serving"), (foods[4], 1.0, "each"), (foods[2], 1.0, "cup")],  # Salmon
        3: [(foods[1], 1.0, "cup"), (foods[0], 1.0, "serving"), (foods[11], 0.5, "each"), (foods[9], 1.0, "cup")],  # Power Bowl
        4: [(foods[10], 1.0, "cup"), (foods[2], 1.0, "cup"), (foods[6], 1.0, "oz")],  # Quinoa Stir-Fry
        5: [(foods[13], 1.0, "serving"), (foods[11], 0.5, "each"), (foods[9], 1.0, "cup")],  # Tuna Wrap
    }
    for idx, ingredients in ingredient_map.items():
        for food, qty, unit in ingredients:
            ri = RecipeIngredient(
                id=_uid(), recipe_id=recipes[idx].id, food_id=food.id,
                name=food.name, quantity=qty, unit=unit,
            )
            db.add(ri)
    db.flush()

    # Meal Plan (1 active, 7 days)
    week_start = _d(0) - timedelta(days=_d(0).weekday())  # Monday of this week
    mp = MealPlan(
        id=_uid(), project_id=pid, user_id=uid,
        name="Balanced Week Plan", week_start=week_start,
        week_end=week_start + timedelta(days=6), is_active=True,
    )
    db.add(mp)
    db.flush()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meals_per_day = [
        ("breakfast", "Overnight Oats", 420),
        ("lunch", "Protein Power Bowl", 580),
        ("dinner", "Salmon with Sweet Potato", 520),
        ("snack", "Greek Yogurt & Almonds", 294),
    ]
    for day in days:
        for meal_type, name, cal in meals_per_day:
            mpe = MealPlanEntry(
                id=_uid(), meal_plan_id=mp.id,
                day=day, meal_type=meal_type, name=name, calories=cal,
            )
            db.add(mpe)
    db.flush()

    # Daily Logs (3 days)
    for days_ago in [2, 1, 0]:
        dl = DailyLog(
            id=_uid(), project_id=pid, user_id=uid,
            date=_d(days_ago),
            calories_consumed=2100 + days_ago * 50,
            calories_target=2200,
            protein=145.0 + days_ago * 3, carbs=255.0 - days_ago * 5,
            fat=72.0 + days_ago, fiber=30.0, water_consumed=7 + days_ago,
            water_target=8, weight=181.0 - days_ago * 0.3,
        )
        db.add(dl)
        db.flush()

        # Meal logs for each daily log
        meal_log_specs = [
            ("breakfast", "Overnight Oats with Blueberries", 420, 28.0, 62.0, 10.0),
            ("lunch", "Grilled Chicken Salad", 380, 42.0, 12.0, 18.0),
            ("dinner", "Salmon with Sweet Potato", 520, 42.0, 35.0, 22.0),
            ("snack", "Greek Yogurt & Almonds", 294, 28.0, 14.0, 14.7),
        ]
        for mtype, mname, cal, prot, carbs, fat in meal_log_specs:
            ml = MealLog(
                id=_uid(), daily_log_id=dl.id,
                meal_type=mtype, name=mname,
                calories=cal, protein=prot, carbs=carbs, fat=fat,
            )
            db.add(ml)
    db.flush()

    # Grocery List (1 with 10 items)
    gl = GroceryList(
        id=_uid(), project_id=pid, user_id=uid,
        name="Weekly Groceries", week_start=week_start, is_active=True,
    )
    db.add(gl)
    db.flush()

    grocery_specs = [
        ("Chicken Breast (boneless)", "Protein", 3.0, "lbs", False),
        ("Salmon Fillets", "Protein", 2.0, "lbs", False),
        ("Brown Rice", "Grains", 2.0, "lbs", True),
        ("Broccoli Crowns", "Vegetables", 2.0, "heads", False),
        ("Sweet Potatoes", "Vegetables", 4.0, "each", False),
        ("Greek Yogurt (32oz)", "Dairy", 2.0, "each", True),
        ("Rolled Oats", "Grains", 1.0, "bag", True),
        ("Fresh Spinach", "Vegetables", 2.0, "bags", False),
        ("Almonds (raw)", "Nuts", 1.0, "bag", False),
        ("Blueberries (fresh)", "Fruits", 2.0, "pints", False),
    ]
    for name, cat, qty, unit, checked in grocery_specs:
        gi = GroceryItem(
            id=_uid(), grocery_list_id=gl.id,
            name=name, category=cat, quantity=qty, unit=unit,
            is_checked=checked,
        )
        db.add(gi)
    db.flush()

    # Weight Entries (5 trending down)
    weights = [184.2, 183.5, 182.8, 182.1, 181.4]
    for i, w in enumerate(weights):
        we = WeightEntry(
            id=_uid(), project_id=pid, user_id=uid,
            date=_d(28 - i * 7), weight=w, unit="lbs",
        )
        db.add(we)
    db.flush()
    print("  -> 1 diet profile, 15 foods, 6 recipes, 1 meal plan (28 entries), 3 daily logs, 1 grocery list, 5 weight entries")


# ---- Finance -------------------------------------------------------------

def seed_finance(db: Session, project: Project, demo: User):
    print("[7/10] Seeding finance (FinanceHub) ...")
    pid = project.id
    uid = demo.id

    # Accounts (4)
    acct_specs = [
        ("Primary Checking", "checking", "****4521", "Chase Bank", Decimal("12450.00"), None, "wallet", "#2563EB"),
        ("High-Yield Savings", "savings", "****8834", "Marcus by Goldman", Decimal("45200.00"), None, "piggy-bank", "#16A34A"),
        ("Investment Portfolio", "investment", "****3310", "Fidelity", Decimal("89500.00"), None, "trending-up", "#7C3AED"),
        ("Visa Platinum", "credit_card", "****9901", "Chase Bank", Decimal("-2340.00"), Decimal("15000.00"), "credit-card", "#DC2626"),
    ]
    accounts = []
    for name, atype, num, inst, balance, limit_, icon, color in acct_specs:
        a = Account(
            id=_uid(), project_id=pid, user_id=uid,
            name=name, account_type=atype, account_number=num,
            institution=inst, balance=balance, credit_limit=limit_,
            icon=icon, color=color,
        )
        db.add(a)
        accounts.append(a)
    db.flush()

    checking, savings, investment, credit = accounts

    # Transactions (15)
    txn_specs = [
        (_d(0), "Monthly Salary Deposit", "TechCorp Inc", Decimal("8500.00"), "income", "income", checking, False, True),
        (_d(1), "Rent Payment", "Parkview Apartments", Decimal("2200.00"), "expense", "housing", checking, False, True),
        (_d(2), "Grocery Shopping", "Whole Foods Market", Decimal("187.45"), "expense", "groceries", checking, False, False),
        (_d(3), "Electric Bill", "PG&E", Decimal("142.30"), "expense", "utilities", checking, False, True),
        (_d(4), "Gas Station", "Shell", Decimal("58.90"), "expense", "transport", credit, False, False),
        (_d(5), "Netflix Subscription", "Netflix", Decimal("15.99"), "expense", "entertainment", credit, False, True),
        (_d(6), "Transfer to Savings", "Internal Transfer", Decimal("2000.00"), "transfer", "transfer", checking, False, False),
        (_d(7), "Restaurant Dinner", "Nopa SF", Decimal("94.50"), "expense", "food", credit, False, False),
        (_d(8), "Freelance Payment", "DesignCo", Decimal("1500.00"), "income", "income", checking, False, False),
        (_d(9), "Gym Membership", "Equinox", Decimal("189.00"), "expense", "health", checking, False, True),
        (_d(10), "Amazon Purchase", "Amazon", Decimal("67.23"), "expense", "shopping", credit, False, False),
        (_d(11), "Uber Ride", "Uber", Decimal("24.50"), "expense", "transport", credit, False, False),
        (_d(12), "Investment Deposit", "Internal Transfer", Decimal("1000.00"), "transfer", "transfer", checking, False, False),
        (_d(13), "Water Bill", "SF Water Dept", Decimal("45.80"), "expense", "utilities", checking, False, True),
        (_d(14), "Coffee Shop", "Blue Bottle", Decimal("12.75"), "expense", "food", credit, False, False),
    ]
    for (dt, desc, merchant, amount, ttype, cat, acct, _, recurring) in txn_specs:
        t = Transaction(
            id=_uid(), project_id=pid, account_id=acct.id, user_id=uid,
            date=dt, description=desc, merchant=merchant, amount=amount,
            transaction_type=ttype, category=cat, is_recurring=recurring,
            transfer_to_account_id=savings.id if desc == "Transfer to Savings" else (
                investment.id if desc == "Investment Deposit" else None
            ),
        )
        db.add(t)
    db.flush()

    # Budgets (5)
    month_start = _d(0).replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    budget_specs = [
        ("Housing", "housing", "home", "#2563EB", Decimal("2500.00"), Decimal("2200.00")),
        ("Food & Dining", "food", "utensils", "#F59E0B", Decimal("600.00"), Decimal("294.70")),
        ("Transportation", "transport", "car", "#10B981", Decimal("300.00"), Decimal("83.40")),
        ("Entertainment", "entertainment", "film", "#8B5CF6", Decimal("200.00"), Decimal("15.99")),
        ("Utilities", "utilities", "zap", "#6366F1", Decimal("250.00"), Decimal("188.10")),
    ]
    for name, cat, icon, color, allocated, spent in budget_specs:
        b = Budget(
            id=_uid(), project_id=pid, user_id=uid,
            name=name, category=cat, icon=icon, color=color,
            allocated=allocated, spent=spent,
            period="monthly", period_start=month_start, period_end=month_end,
        )
        db.add(b)
    db.flush()

    # Finance Invoices (4)
    finv_specs = [
        ("FI-2024-001", "Acme Corp", "billing@acme.com", Decimal("5000.00"), Decimal("5000.00"), "paid", _d(30), _d(0), _d(5)),
        ("FI-2024-002", "Globex Inc", "ap@globex.io", Decimal("3200.00"), Decimal("0.00"), "pending", _d(15), _d(-15), None),
        ("FI-2024-003", "TechStart", "finance@techstart.co", Decimal("1800.00"), Decimal("1800.00"), "paid", _d(45), _d(15), _d(20)),
        ("FI-2024-004", "CloudNine", "pay@cloudnine.io", Decimal("4500.00"), Decimal("0.00"), "overdue", _d(60), _d(-5), None),
    ]
    for inv_num, client, email, amount, paid, status, issued, due, paid_date in finv_specs:
        fi = FinanceInvoice(
            id=_uid(), project_id=pid, user_id=uid,
            invoice_number=inv_num, client_name=client, client_email=email,
            amount=amount, amount_paid=paid, status=status,
            issued_date=issued, due_date=due, paid_date=paid_date,
            line_items=[
                {"description": "Consulting Services", "hours": 20, "rate": float(amount) / 20, "total": float(amount)},
            ],
        )
        db.add(fi)
    db.flush()

    # Financial Report (1 P&L snapshot)
    report = FinancialReport(
        id=_uid(), project_id=pid,
        report_type="profit_and_loss",
        period_start=_d(90), period_end=_d(0),
        revenue=Decimal("45200.00"), cogs=Decimal("12800.00"),
        gross_profit=Decimal("32400.00"), operating_expenses=Decimal("18500.00"),
        net_income=Decimal("13900.00"),
        operating_cash_flow=Decimal("15200.00"),
        investing_cash_flow=Decimal("-3000.00"),
        financing_cash_flow=Decimal("-1500.00"),
        net_cash_change=Decimal("10700.00"),
        expense_breakdown={
            "salaries": 8500, "rent": 4200, "utilities": 1800,
            "marketing": 2400, "software": 1600,
        },
        ratios={
            "gross_margin": 0.717, "net_margin": 0.308,
            "operating_margin": 0.308, "current_ratio": 2.4,
        },
        yoy_comparison={
            "revenue_growth": 0.12, "expense_growth": 0.08,
            "profit_growth": 0.18,
        },
    )
    db.add(report)
    db.flush()
    print("  -> 4 accounts, 15 transactions, 5 budgets, 4 invoices, 1 report")


# ---- Blog ----------------------------------------------------------------

def seed_blog(db: Session, project: Project, demo: User):
    print("[8/10] Seeding blog (NutriTrack) ...")

    # Categories (3)
    cat_specs = [
        ("Nutrition", "nutrition", "Articles about nutrition science and tips"),
        ("Recipes", "recipes", "Healthy recipes and meal ideas"),
        ("Fitness", "fitness", "Workout tips and fitness guidance"),
    ]
    categories = []
    for name, slug, desc in cat_specs:
        c = Category(
            id=_uid(), name=name, slug=slug, description=desc,
        )
        db.add(c)
        categories.append(c)
    db.flush()

    # Tags (5)
    tag_specs = [
        ("healthy-eating", "healthy-eating"),
        ("meal-prep", "meal-prep"),
        ("protein", "protein"),
        ("weight-loss", "weight-loss"),
        ("recipes", "recipes-tag"),
    ]
    tags = []
    for name, slug in tag_specs:
        t = Tag(id=_uid(), name=name, slug=slug)
        db.add(t)
        tags.append(t)
    db.flush()

    # Posts (4)
    post_specs = [
        ("10 High-Protein Meals for Busy Weeknights", "10-high-protein-meals",
         "Quick and easy high-protein dinner ideas you can make in under 30 minutes.",
         "Eating enough protein is essential for muscle recovery and staying full throughout the evening. "
         "Here are 10 meals that pack 40g+ of protein and take less than 30 minutes to prepare...",
         categories[1], [tags[0], tags[2], tags[4]], True),
        ("Understanding Macronutrients: A Beginner's Guide", "understanding-macronutrients",
         "Everything you need to know about proteins, carbs, and fats.",
         "Macronutrients are the three main categories of nutrients your body needs in large amounts. "
         "Protein builds and repairs tissue, carbohydrates provide energy, and fats support cell growth...",
         categories[0], [tags[0], tags[3]], False),
        ("The Ultimate Meal Prep Guide", "ultimate-meal-prep-guide",
         "How to plan, prep, and store a full week of healthy meals.",
         "Meal prepping saves time, reduces food waste, and helps you stick to your nutrition goals. "
         "Start by choosing 3-4 proteins, 2-3 grains, and 4-5 vegetables for the week...",
         categories[1], [tags[1], tags[4]], True),
        ("How to Track Calories Without Obsessing", "track-calories-without-obsessing",
         "A balanced approach to calorie counting that supports your goals without stress.",
         "Calorie tracking can be a powerful tool when used mindfully. The key is to focus on trends "
         "rather than exact numbers, and to use tracking as a learning tool rather than a strict rule...",
         categories[0], [tags[0], tags[3]], False),
    ]
    for title, slug, excerpt, content, cat, post_tags_list, featured in post_specs:
        p = Post(
            id=_uid(), title=title, slug=slug, excerpt=excerpt,
            content=content, status="published",
            published_at=_dt(len(post_specs) * 3),
            author_id=demo.id, category_id=cat.id,
            is_featured=featured, allow_comments=True,
        )
        db.add(p)
        db.flush()
        # Add tags via the association table
        for tag in post_tags_list:
            db.execute(
                post_tags.insert().values(post_id=p.id, tag_id=tag.id)
            )
    db.flush()
    print("  -> 3 categories, 5 tags, 4 posts")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Seed all domains with realistic data. Idempotent."""
    print("=" * 60)
    print("  VA Studio - Database Seed Script")
    print("=" * 60)

    # Ensure all ORM models are registered on Base.metadata
    discover_orm_models()

    Session = get_sync_session_factory()
    if Session is None:
        print("ERROR: Could not create sync session factory. Check DB config.")
        sys.exit(1)

    db = Session()
    try:
        # Idempotency check
        existing = db.query(User).filter(User.email == "admin@vastudio.com").first()
        if existing:
            print("\n[SKIP] Seed data already exists (admin@vastudio.com found). Exiting.")
            print("  To re-seed, delete existing seed data first.")
            return

        admin, demo = seed_users(db)
        projects = seed_projects(db, demo)

        seed_ecommerce(db, projects["va-store"], demo)
        seed_crm(db, projects["sales-crm"], demo)
        seed_erp(db, projects["nexus-erp"], demo)
        seed_nutrition(db, projects["nutritrack"], demo)
        seed_finance(db, projects["financehub"], demo)
        seed_blog(db, projects["nutritrack"], demo)

        db.commit()

        print()
        print("=" * 60)
        print("  Seeding completed successfully!")
        print("=" * 60)
        print()
        print("  Credentials:")
        print("    Admin: admin@vastudio.com / Admin123!")
        print("    Demo:  demo@vastudio.com  / Demo123!")
        print()
        print("  Projects: VA Store, Sales CRM, Nexus ERP, NutriTrack, FinanceHub")
        print()

    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
