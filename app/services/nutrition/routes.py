"""
Nutrition Routes

Diet profiles, foods, recipes, meal plans, daily logs, grocery lists,
weight tracking, achievements - user-scoped with project_id as query param.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.auth.dependencies import get_current_active_user
from app.orm.user import User
from app.orm.nutrition import (
    DietProfile,
    Food,
    Recipe,
    RecipeIngredient,
    MealPlan,
    MealPlanEntry,
    DailyLog,
    MealLog,
    GroceryList,
    GroceryItem,
    WeightEntry,
    Achievement,
    UserAchievement,
)
from app.schemas.nutrition import (
    DietProfileCreate,
    DietProfileUpdate,
    DietProfileResponse,
    FoodCreate,
    FoodResponse,
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
    RecipeIngredientCreate,
    MealPlanCreate,
    MealPlanUpdate,
    MealPlanResponse,
    MealPlanEntryCreate,
    DailyLogCreate,
    DailyLogUpdate,
    DailyLogResponse,
    MealLogCreate,
    MealLogResponse,
    GroceryListCreate,
    GroceryListResponse,
    GroceryItemUpdate,
    GroceryItemResponse,
    WeightEntryCreate,
    WeightEntryResponse,
    AchievementResponse,
    UserAchievementResponse,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/nutrition", tags=["Nutrition"])


# ---------------------------------------------------------------------------
# Diet Profile (user-scoped, one per user per project)
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=DietProfileResponse)
async def get_diet_profile(
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get the current user's diet profile."""
    result = await db.execute(
        select(DietProfile).where(
            DietProfile.user_id == current_user.id,
            DietProfile.project_id == project_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Diet profile not found")
    return profile


@router.post(
    "/profile",
    response_model=DietProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_diet_profile(
    data: DietProfileCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a diet profile for the current user."""
    existing = await db.execute(
        select(DietProfile).where(
            DietProfile.user_id == current_user.id,
            DietProfile.project_id == project_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Diet profile already exists. Use PATCH to update.",
        )
    profile = DietProfile(
        project_id=project_id,
        user_id=current_user.id,
        diet_type=data.diet_type,
        goal=data.goal,
        calorie_target=data.calorie_target,
        protein_target=data.protein_target,
        carbs_target=data.carbs_target,
        fat_target=data.fat_target,
        fiber_target=data.fiber_target,
        water_target=data.water_target,
        current_weight=data.current_weight,
        target_weight=data.target_weight,
        height=data.height,
        restrictions=data.restrictions,
        allergies=data.allergies,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.patch("/profile", response_model=DietProfileResponse)
async def update_diet_profile(
    data: DietProfileUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update the current user's diet profile."""
    result = await db.execute(
        select(DietProfile).where(
            DietProfile.user_id == current_user.id,
            DietProfile.project_id == project_id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Diet profile not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(profile, k, v)
    await db.commit()
    await db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Foods
# ---------------------------------------------------------------------------

@router.get("/foods", response_model=PaginatedResponse[FoodResponse])
async def list_foods(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List foods for a project."""
    skip = (page - 1) * per_page
    query = select(Food).where(Food.project_id == project_id)
    if category:
        query = query.where(Food.category == category)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Food.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/foods",
    response_model=FoodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_food(
    data: FoodCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a food item."""
    food = Food(
        project_id=project_id,
        name=data.name,
        brand=data.brand,
        barcode=data.barcode,
        category=data.category,
        serving_size=data.serving_size,
        serving_unit=data.serving_unit,
        calories=data.calories,
        protein=data.protein,
        carbs=data.carbs,
        fat=data.fat,
        fiber=data.fiber,
        sugar=data.sugar,
        sodium=data.sodium,
        is_custom=data.is_custom,
    )
    db.add(food)
    await db.commit()
    await db.refresh(food)
    return food


@router.get("/foods/search", response_model=PaginatedResponse[FoodResponse])
async def search_foods(
    q: str = Query(..., min_length=1, description="Search query"),
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Search foods by name."""
    skip = (page - 1) * per_page
    query = select(Food).where(
        Food.project_id == project_id,
        Food.name.ilike(f"%{q}%"),
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Food.name)
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------

@router.get("/recipes", response_model=PaginatedResponse[RecipeResponse])
async def list_recipes(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List recipes."""
    skip = (page - 1) * per_page
    query = select(Recipe).where(
        Recipe.project_id == project_id,
        Recipe.is_deleted == False,
    )
    if category:
        query = query.where(Recipe.category == category)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Recipe.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/recipes",
    response_model=RecipeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recipe(
    data: RecipeCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a recipe with ingredients."""
    ingredients = [
        RecipeIngredient(
            name=ing.name,
            quantity=ing.quantity,
            unit=ing.unit,
            food_id=ing.food_id,
        )
        for ing in data.ingredients
    ]
    recipe = Recipe(
        project_id=project_id,
        user_id=current_user.id,
        title=data.title,
        description=data.description,
        category=data.category,
        image=data.image,
        prep_time=data.prep_time,
        cook_time=data.cook_time,
        servings=data.servings,
        difficulty=data.difficulty,
        calories=data.calories,
        protein=data.protein,
        carbs=data.carbs,
        fat=data.fat,
        instructions=data.instructions,
        ingredients=ingredients,
    )
    db.add(recipe)
    await db.commit()
    await db.refresh(recipe)
    return recipe


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a recipe by ID."""
    result = await db.execute(
        select(Recipe).where(
            Recipe.id == recipe_id,
            Recipe.project_id == project_id,
            Recipe.is_deleted == False,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.patch("/recipes/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: str,
    data: RecipeUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a recipe."""
    result = await db.execute(
        select(Recipe).where(
            Recipe.id == recipe_id,
            Recipe.project_id == project_id,
            Recipe.is_deleted == False,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    update_data = data.model_dump(exclude_unset=True)
    # Handle ingredients replacement if provided
    if "ingredients" in update_data:
        new_ingredients = update_data.pop("ingredients")
        if new_ingredients is not None:
            # Clear existing and add new
            recipe.ingredients.clear()
            for ing in new_ingredients:
                recipe.ingredients.append(
                    RecipeIngredient(
                        name=ing["name"],
                        quantity=ing.get("quantity", 1.0),
                        unit=ing.get("unit"),
                        food_id=ing.get("food_id"),
                    )
                )
    for k, v in update_data.items():
        setattr(recipe, k, v)
    await db.commit()
    await db.refresh(recipe)
    return recipe


@router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soft-delete a recipe."""
    result = await db.execute(
        select(Recipe).where(
            Recipe.id == recipe_id,
            Recipe.project_id == project_id,
            Recipe.is_deleted == False,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe.soft_delete()
    await db.commit()
    return {"message": "Recipe deleted"}


# ---------------------------------------------------------------------------
# Meal Plans
# ---------------------------------------------------------------------------

@router.get("/meal-plans", response_model=PaginatedResponse[MealPlanResponse])
async def list_meal_plans(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List meal plans for the current user."""
    skip = (page - 1) * per_page
    query = select(MealPlan).where(
        MealPlan.user_id == current_user.id,
        MealPlan.project_id == project_id,
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(MealPlan.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/meal-plans",
    response_model=MealPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_meal_plan(
    data: MealPlanCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a meal plan with entries."""
    entries = [
        MealPlanEntry(
            day=e.day,
            meal_type=e.meal_type,
            name=e.name,
            calories=e.calories,
            recipe_id=e.recipe_id,
        )
        for e in data.entries
    ]
    plan = MealPlan(
        project_id=project_id,
        user_id=current_user.id,
        name=data.name,
        week_start=data.week_start,
        week_end=data.week_end,
        entries=entries,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/meal-plans/{plan_id}", response_model=MealPlanResponse)
async def get_meal_plan(
    plan_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a meal plan by ID."""
    result = await db.execute(
        select(MealPlan).where(
            MealPlan.id == plan_id,
            MealPlan.user_id == current_user.id,
            MealPlan.project_id == project_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    return plan


@router.patch("/meal-plans/{plan_id}", response_model=MealPlanResponse)
async def update_meal_plan(
    plan_id: str,
    data: MealPlanUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a meal plan."""
    result = await db.execute(
        select(MealPlan).where(
            MealPlan.id == plan_id,
            MealPlan.user_id == current_user.id,
            MealPlan.project_id == project_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    await db.commit()
    await db.refresh(plan)
    return plan


# ---------------------------------------------------------------------------
# Daily Logs
# ---------------------------------------------------------------------------

@router.get("/daily-logs", response_model=PaginatedResponse[DailyLogResponse])
async def list_daily_logs(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    date_filter: Optional[date] = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List daily logs for the current user. Optionally filter by date."""
    skip = (page - 1) * per_page
    query = select(DailyLog).where(
        DailyLog.user_id == current_user.id,
        DailyLog.project_id == project_id,
    )
    if date_filter:
        query = query.where(DailyLog.date == date_filter)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(DailyLog.date.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/daily-logs",
    response_model=DailyLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_daily_log(
    data: DailyLogCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a daily log."""
    log = DailyLog(
        project_id=project_id,
        user_id=current_user.id,
        date=data.date,
        calories_target=data.calories_target,
        water_target=data.water_target,
        notes=data.notes,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.get("/daily-logs/{log_id}", response_model=DailyLogResponse)
async def get_daily_log(
    log_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a daily log by ID."""
    result = await db.execute(
        select(DailyLog).where(
            DailyLog.id == log_id,
            DailyLog.user_id == current_user.id,
            DailyLog.project_id == project_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Daily log not found")
    return log


@router.patch("/daily-logs/{log_id}", response_model=DailyLogResponse)
async def update_daily_log(
    log_id: str,
    data: DailyLogUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a daily log."""
    result = await db.execute(
        select(DailyLog).where(
            DailyLog.id == log_id,
            DailyLog.user_id == current_user.id,
            DailyLog.project_id == project_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Daily log not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(log, k, v)
    await db.commit()
    await db.refresh(log)
    return log


@router.post(
    "/daily-logs/{log_id}/meals",
    response_model=MealLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_meal_to_daily_log(
    log_id: str,
    data: MealLogCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Add a meal entry to a daily log."""
    result = await db.execute(
        select(DailyLog).where(
            DailyLog.id == log_id,
            DailyLog.user_id == current_user.id,
            DailyLog.project_id == project_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Daily log not found")
    meal = MealLog(
        daily_log_id=log.id,
        meal_type=data.meal_type,
        name=data.name,
        servings=data.servings,
        calories=data.calories,
        protein=data.protein,
        carbs=data.carbs,
        fat=data.fat,
        food_id=data.food_id,
        recipe_id=data.recipe_id,
    )
    db.add(meal)
    # Update daily log totals
    log.calories_consumed += data.calories
    log.protein += data.protein
    log.carbs += data.carbs
    log.fat += data.fat
    await db.commit()
    await db.refresh(meal)
    return meal


# ---------------------------------------------------------------------------
# Grocery Lists
# ---------------------------------------------------------------------------

@router.get("/grocery-lists", response_model=PaginatedResponse[GroceryListResponse])
async def list_grocery_lists(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List grocery lists for the current user."""
    skip = (page - 1) * per_page
    query = select(GroceryList).where(
        GroceryList.user_id == current_user.id,
        GroceryList.project_id == project_id,
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(GroceryList.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/grocery-lists",
    response_model=GroceryListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_grocery_list(
    data: GroceryListCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a grocery list with items."""
    items = [
        GroceryItem(
            name=i.name,
            category=i.category,
            quantity=i.quantity,
            unit=i.unit,
        )
        for i in data.items
    ]
    grocery_list = GroceryList(
        project_id=project_id,
        user_id=current_user.id,
        name=data.name,
        week_start=data.week_start,
        items=items,
    )
    db.add(grocery_list)
    await db.commit()
    await db.refresh(grocery_list)
    return grocery_list


@router.get("/grocery-lists/{list_id}", response_model=GroceryListResponse)
async def get_grocery_list(
    list_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a grocery list by ID."""
    result = await db.execute(
        select(GroceryList).where(
            GroceryList.id == list_id,
            GroceryList.user_id == current_user.id,
            GroceryList.project_id == project_id,
        )
    )
    grocery_list = result.scalar_one_or_none()
    if not grocery_list:
        raise HTTPException(status_code=404, detail="Grocery list not found")
    return grocery_list


@router.patch("/grocery-lists/{list_id}", response_model=GroceryListResponse)
async def update_grocery_list(
    list_id: str,
    data: GroceryListCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a grocery list (name, week_start)."""
    result = await db.execute(
        select(GroceryList).where(
            GroceryList.id == list_id,
            GroceryList.user_id == current_user.id,
            GroceryList.project_id == project_id,
        )
    )
    grocery_list = result.scalar_one_or_none()
    if not grocery_list:
        raise HTTPException(status_code=404, detail="Grocery list not found")
    if data.name is not None:
        grocery_list.name = data.name
    if data.week_start is not None:
        grocery_list.week_start = data.week_start
    await db.commit()
    await db.refresh(grocery_list)
    return grocery_list


@router.patch(
    "/grocery-lists/{list_id}/items/{item_id}",
    response_model=GroceryItemResponse,
)
async def toggle_grocery_item(
    list_id: str,
    item_id: str,
    data: GroceryItemUpdate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Toggle or update a grocery list item."""
    # Verify ownership
    result = await db.execute(
        select(GroceryList).where(
            GroceryList.id == list_id,
            GroceryList.user_id == current_user.id,
            GroceryList.project_id == project_id,
        )
    )
    grocery_list = result.scalar_one_or_none()
    if not grocery_list:
        raise HTTPException(status_code=404, detail="Grocery list not found")
    # Find the item
    result = await db.execute(
        select(GroceryItem).where(
            GroceryItem.id == item_id,
            GroceryItem.grocery_list_id == list_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Grocery item not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Weight Entries
# ---------------------------------------------------------------------------

@router.get("/weight", response_model=PaginatedResponse[WeightEntryResponse])
async def list_weight_entries(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List weight entries for the current user."""
    skip = (page - 1) * per_page
    query = select(WeightEntry).where(
        WeightEntry.user_id == current_user.id,
        WeightEntry.project_id == project_id,
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(WeightEntry.date.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)


@router.post(
    "/weight",
    response_model=WeightEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_weight_entry(
    data: WeightEntryCreate,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a weight entry."""
    entry = WeightEntry(
        project_id=project_id,
        user_id=current_user.id,
        date=data.date,
        weight=data.weight,
        unit=data.unit,
        notes=data.notes,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------

@router.get("/achievements", response_model=PaginatedResponse[AchievementResponse])
async def list_achievements(
    project_id: str = Query(..., description="Project ID"),
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List achievements for the project."""
    skip = (page - 1) * per_page
    query = select(Achievement).where(Achievement.project_id == project_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()
    query = query.offset(skip).limit(per_page).order_by(Achievement.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())
    return PaginatedResponse.create(items=items, total=total, page=page, per_page=per_page)
