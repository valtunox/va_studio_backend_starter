"""
Nutrition / Diet Models

Foods, recipes, meals, meal plans, daily logs, grocery lists,
diet profiles, weight tracking, achievements —
scoped by project_id for multi-use-case backend.

Matches the frontend diet + nutritionapp template data structures:
  diet profile (calories/macros targets), daily meals, food database,
  recipes (with ingredients), meal plans (weekly), grocery lists,
  weight progress, water intake, achievements/streaks.
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

class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class GoalType(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    WEIGHT_GAIN = "weight_gain"
    MAINTENANCE = "maintenance"
    MUSCLE_GAIN = "muscle_gain"


class DietType(str, Enum):
    BALANCED = "balanced"
    KETO = "keto"
    VEGAN = "vegan"
    VEGETARIAN = "vegetarian"
    PALEO = "paleo"
    MEDITERRANEAN = "mediterranean"
    LOW_CARB = "low_carb"
    HIGH_PROTEIN = "high_protein"


# ---------------------------------------------------------------------------
# Diet Profile — user's nutrition goals and preferences
# ---------------------------------------------------------------------------

class DietProfile(Base, TimestampMixin):
    """Per-user nutrition goals, targets, and dietary preferences."""

    __tablename__ = "diet_profiles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Goals
    diet_type: Mapped[str] = mapped_column(
        String(30), default=DietType.BALANCED.value, nullable=False,
    )
    goal: Mapped[str] = mapped_column(
        String(30), default=GoalType.MAINTENANCE.value, nullable=False,
    )

    # Calorie target
    calorie_target: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)

    # Macro targets (grams)
    protein_target: Mapped[int] = mapped_column(Integer, default=130, nullable=False)
    carbs_target: Mapped[int] = mapped_column(Integer, default=250, nullable=False)
    fat_target: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    fiber_target: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # Water target (glasses)
    water_target: Mapped[int] = mapped_column(Integer, default=8, nullable=False)

    # Body stats
    current_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    height: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Dietary restrictions (JSON array of strings)
    restrictions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    allergies: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


# ---------------------------------------------------------------------------
# Food — database of foods with nutritional info
# ---------------------------------------------------------------------------

class Food(Base, TimestampMixin):
    """Food item with nutritional data per serving."""

    __tablename__ = "foods"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Serving info
    serving_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    serving_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Nutrition per serving
    calories: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    protein: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    carbs: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fat: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fiber: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sugar: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sodium: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------

class Recipe(Base, TimestampMixin, SoftDeleteMixin):
    """Recipe with prep info and nutrition totals."""

    __tablename__ = "recipes"

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

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Prep info
    prep_time: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cook_time: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    servings: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    difficulty: Mapped[str] = mapped_column(
        String(20), default=DifficultyLevel.EASY.value, nullable=False,
    )

    # Nutrition per serving
    calories: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    protein: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    carbs: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fat: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Social
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Instructions (JSON array of step strings)
    instructions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    ingredients: Mapped[List["RecipeIngredient"]] = relationship(
        "RecipeIngredient", back_populates="recipe", lazy="selectin",
        cascade="all, delete-orphan",
    )


class RecipeIngredient(Base, TimestampMixin):
    """Ingredient line in a recipe."""

    __tablename__ = "recipe_ingredients"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    recipe_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    food_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("foods.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    recipe: Mapped["Recipe"] = relationship("Recipe", back_populates="ingredients")


# ---------------------------------------------------------------------------
# Meal Plan
# ---------------------------------------------------------------------------

class MealPlan(Base, TimestampMixin):
    """Weekly meal plan — 7 days of breakfast/lunch/dinner/snack."""

    __tablename__ = "meal_plans"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    week_start: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    week_end: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    entries: Mapped[List["MealPlanEntry"]] = relationship(
        "MealPlanEntry", back_populates="meal_plan", lazy="selectin",
        cascade="all, delete-orphan",
    )


class MealPlanEntry(Base, TimestampMixin):
    """Single slot in a meal plan (e.g., Monday breakfast)."""

    __tablename__ = "meal_plan_entries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    meal_plan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("meal_plans.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    recipe_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
    )

    day: Mapped[str] = mapped_column(String(20), nullable=False)
    meal_type: Mapped[str] = mapped_column(
        String(20), default=MealType.BREAKFAST.value, nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    calories: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    meal_plan: Mapped["MealPlan"] = relationship("MealPlan", back_populates="entries")


# ---------------------------------------------------------------------------
# Daily Log — tracks meals, water, weight for a single day
# ---------------------------------------------------------------------------

class DailyLog(Base, TimestampMixin):
    """Daily nutrition log — calories consumed, water, weight."""

    __tablename__ = "daily_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    date: Mapped[str] = mapped_column(Date, nullable=False, index=True)

    # Calorie summary
    calories_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    calories_target: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)

    # Macros consumed
    protein: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    carbs: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fat: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fiber: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Water (glasses)
    water_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    water_target: Mapped[int] = mapped_column(Integer, default=8, nullable=False)

    # Weight (optional daily weigh-in)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Mood / notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    meals: Mapped[List["MealLog"]] = relationship(
        "MealLog", back_populates="daily_log", lazy="selectin",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Meal Log — individual meal entry within a daily log
# ---------------------------------------------------------------------------

class MealLog(Base, TimestampMixin):
    """Single meal logged (e.g., 'Breakfast — Spinach Omelet, 340 cal')."""

    __tablename__ = "meal_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    daily_log_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("daily_logs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    food_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("foods.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipe_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
    )

    meal_type: Mapped[str] = mapped_column(
        String(20), default=MealType.BREAKFAST.value, nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    servings: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Nutrition for this entry
    calories: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    protein: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    carbs: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fat: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    daily_log: Mapped["DailyLog"] = relationship("DailyLog", back_populates="meals")


# ---------------------------------------------------------------------------
# Grocery List
# ---------------------------------------------------------------------------

class GroceryList(Base, TimestampMixin):
    """Grocery list — generated from meal plans or manual."""

    __tablename__ = "grocery_lists"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    week_start: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")
    items: Mapped[List["GroceryItem"]] = relationship(
        "GroceryItem", back_populates="grocery_list", lazy="selectin",
        cascade="all, delete-orphan",
    )


class GroceryItem(Base, TimestampMixin):
    """Single item on a grocery list."""

    __tablename__ = "grocery_items"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    grocery_list_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("grocery_lists.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    grocery_list: Mapped["GroceryList"] = relationship("GroceryList", back_populates="items")


# ---------------------------------------------------------------------------
# Weight Entry — historical weight tracking
# ---------------------------------------------------------------------------

class WeightEntry(Base, TimestampMixin):
    """Daily weight log entry for progress tracking."""

    __tablename__ = "weight_entries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    date: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(5), default="lbs", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


# ---------------------------------------------------------------------------
# Achievement
# ---------------------------------------------------------------------------

class Achievement(Base, TimestampMixin):
    """Achievement / badge definition."""

    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    criteria: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    project: Mapped["Project"] = relationship("Project", lazy="selectin")


class UserAchievement(Base, TimestampMixin):
    """Tracks which achievements a user has earned."""

    __tablename__ = "user_achievements"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    achievement_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    earned_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
