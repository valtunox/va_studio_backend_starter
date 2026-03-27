"""Nutrition / Diet schemas — foods, recipes, meals, plans, logs, grocery lists, progress."""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Diet Profile
# ---------------------------------------------------------------------------

class DietProfileBase(BaseModel):
    diet_type: str = "balanced"
    goal: str = "maintenance"
    calorie_target: int = Field(2000, ge=500, le=10000)
    protein_target: int = Field(130, ge=0)
    carbs_target: int = Field(250, ge=0)
    fat_target: int = Field(70, ge=0)
    fiber_target: int = Field(30, ge=0)
    water_target: int = Field(8, ge=0)
    current_weight: Optional[float] = None
    target_weight: Optional[float] = None
    height: Optional[float] = None
    restrictions: Optional[list] = None
    allergies: Optional[list] = None


class DietProfileCreate(DietProfileBase):
    pass


class DietProfileUpdate(BaseModel):
    diet_type: Optional[str] = None
    goal: Optional[str] = None
    calorie_target: Optional[int] = Field(None, ge=500, le=10000)
    protein_target: Optional[int] = None
    carbs_target: Optional[int] = None
    fat_target: Optional[int] = None
    fiber_target: Optional[int] = None
    water_target: Optional[int] = None
    current_weight: Optional[float] = None
    target_weight: Optional[float] = None
    height: Optional[float] = None
    restrictions: Optional[list] = None
    allergies: Optional[list] = None


class DietProfileResponse(DietProfileBase):
    id: str
    project_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Food
# ---------------------------------------------------------------------------

class FoodBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    brand: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    serving_size: Optional[str] = None
    serving_unit: Optional[str] = None
    calories: int = Field(0, ge=0)
    protein: float = Field(0.0, ge=0)
    carbs: float = Field(0.0, ge=0)
    fat: float = Field(0.0, ge=0)
    fiber: float = Field(0.0, ge=0)
    sugar: float = Field(0.0, ge=0)
    sodium: float = Field(0.0, ge=0)


class FoodCreate(FoodBase):
    is_custom: bool = False


class FoodUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    brand: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    serving_size: Optional[str] = None
    serving_unit: Optional[str] = None
    calories: Optional[int] = Field(None, ge=0)
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    fiber: Optional[float] = None
    sugar: Optional[float] = None
    sodium: Optional[float] = None


class FoodResponse(FoodBase):
    id: str
    project_id: str
    is_custom: bool = False
    image: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------

class RecipeIngredientCreate(BaseModel):
    name: str = Field(..., max_length=255)
    quantity: float = 1.0
    unit: Optional[str] = None
    food_id: Optional[str] = None


class RecipeIngredientResponse(BaseModel):
    id: str
    name: str
    quantity: float
    unit: Optional[str] = None
    food_id: Optional[str] = None

    model_config = {"from_attributes": True}


class RecipeBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    image: Optional[str] = None
    prep_time: int = Field(0, ge=0)
    cook_time: int = Field(0, ge=0)
    servings: int = Field(1, ge=1)
    difficulty: str = "easy"
    calories: int = Field(0, ge=0)
    protein: float = Field(0.0, ge=0)
    carbs: float = Field(0.0, ge=0)
    fat: float = Field(0.0, ge=0)
    instructions: Optional[list] = None


class RecipeCreate(RecipeBase):
    ingredients: List[RecipeIngredientCreate] = []


class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    image: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    servings: Optional[int] = None
    difficulty: Optional[str] = None
    calories: Optional[int] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    instructions: Optional[list] = None
    ingredients: Optional[List[RecipeIngredientCreate]] = None


class RecipeResponse(RecipeBase):
    id: str
    project_id: str
    user_id: Optional[str] = None
    rating: float = 0.0
    is_featured: bool = False
    ingredients: List[RecipeIngredientResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Meal Plan
# ---------------------------------------------------------------------------

class MealPlanEntryCreate(BaseModel):
    day: str = Field(..., max_length=20)
    meal_type: str = "breakfast"
    name: str = Field(..., max_length=255)
    calories: int = 0
    recipe_id: Optional[str] = None


class MealPlanEntryResponse(BaseModel):
    id: str
    day: str
    meal_type: str
    name: str
    calories: int
    recipe_id: Optional[str] = None

    model_config = {"from_attributes": True}


class MealPlanCreate(BaseModel):
    name: Optional[str] = None
    week_start: Optional[date] = None
    week_end: Optional[date] = None
    entries: List[MealPlanEntryCreate] = []


class MealPlanUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class MealPlanResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    name: Optional[str] = None
    week_start: Optional[date] = None
    week_end: Optional[date] = None
    is_active: bool = True
    entries: List[MealPlanEntryResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Daily Log
# ---------------------------------------------------------------------------

class MealLogCreate(BaseModel):
    meal_type: str = "breakfast"
    name: str = Field(..., max_length=255)
    servings: float = 1.0
    calories: int = 0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    food_id: Optional[str] = None
    recipe_id: Optional[str] = None


class MealLogResponse(BaseModel):
    id: str
    meal_type: str
    name: str
    servings: float
    calories: int
    protein: float
    carbs: float
    fat: float
    food_id: Optional[str] = None
    recipe_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DailyLogCreate(BaseModel):
    date: date
    calories_target: int = 2000
    water_target: int = 8
    notes: Optional[str] = None


class DailyLogUpdate(BaseModel):
    calories_consumed: Optional[int] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    fiber: Optional[float] = None
    water_consumed: Optional[int] = None
    weight: Optional[float] = None
    notes: Optional[str] = None


class DailyLogResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    date: date
    calories_consumed: int = 0
    calories_target: int = 2000
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    fiber: float = 0.0
    water_consumed: int = 0
    water_target: int = 8
    weight: Optional[float] = None
    notes: Optional[str] = None
    meals: List[MealLogResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Grocery List
# ---------------------------------------------------------------------------

class GroceryItemCreate(BaseModel):
    name: str = Field(..., max_length=255)
    category: Optional[str] = None
    quantity: float = 1.0
    unit: Optional[str] = None


class GroceryItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    is_checked: Optional[bool] = None


class GroceryItemResponse(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    quantity: float
    unit: Optional[str] = None
    is_checked: bool = False

    model_config = {"from_attributes": True}


class GroceryListCreate(BaseModel):
    name: Optional[str] = None
    week_start: Optional[date] = None
    items: List[GroceryItemCreate] = []


class GroceryListResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    name: Optional[str] = None
    week_start: Optional[date] = None
    is_active: bool = True
    items: List[GroceryItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Weight Entry
# ---------------------------------------------------------------------------

class WeightEntryCreate(BaseModel):
    date: date
    weight: float = Field(..., gt=0)
    unit: str = "lbs"
    notes: Optional[str] = None


class WeightEntryResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    date: date
    weight: float
    unit: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Achievement
# ---------------------------------------------------------------------------

class AchievementResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None

    model_config = {"from_attributes": True}


class UserAchievementResponse(BaseModel):
    id: str
    user_id: str
    achievement_id: str
    earned_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
