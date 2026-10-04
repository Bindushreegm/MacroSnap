import streamlit as st
import sqlite3
import json
import re
import time
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
from google import genai
from google.genai import types 


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="MacroSnap",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# CONSTANTS
# =========================================================

DB_FILE = "macrosnap.db"
MODEL_NAME = "gemini-3.8-flash"

MEAL_TYPES = [
    "Breakfast",
    "Lunch",
    "Dinner",
    "Snack"
]

GOALS = [
    "Fat Loss",
    "Muscle Gain",
    "Maintenance",
    "General Healthy Eating"
]

ACTIVITY_LEVELS = [
    "Sedentary",
    "Lightly Active",
    "Moderately Active",
    "Very Active"
]

DIET_TYPES = [
    "Vegetarian",
    "Non-Vegetarian",
    "Vegan",
    "Eggetarian"
]


# =========================================================
# DATABASE
# =========================================================

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def init_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_type TEXT NOT NULL,
            food_name TEXT NOT NULL,
            calories REAL DEFAULT 0,
            protein REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            portion TEXT DEFAULT '',
            meal_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            goal TEXT DEFAULT '',
            age INTEGER DEFAULT 0,
            height_cm REAL DEFAULT 0,
            weight_kg REAL DEFAULT 0,
            gender TEXT DEFAULT '',
            activity_level TEXT DEFAULT '',
            diet_type TEXT DEFAULT '',
            food_preferences TEXT DEFAULT '',
            food_restrictions TEXT DEFAULT '',
            usual_meals TEXT DEFAULT '',
            main_difficulty TEXT DEFAULT '',
            calorie_target REAL DEFAULT 0,
            protein_target REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def upgrade_database():

    """
    Safely upgrades older MacroSnap databases.

    IMPORTANT:
    SQLite does NOT allow CURRENT_TIMESTAMP as a DEFAULT
    when using ALTER TABLE ADD COLUMN.

    Therefore missing columns use simple constant defaults.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(profile)")
    columns = [row[1] for row in cursor.fetchall()]

    if "calorie_target" not in columns:
        cursor.execute("""
            ALTER TABLE profile
            ADD COLUMN calorie_target REAL DEFAULT 0
        """)

    if "protein_target" not in columns:
        cursor.execute("""
            ALTER TABLE profile
            ADD COLUMN protein_target REAL DEFAULT 0
        """)

    if "food_preferences" not in columns:
        cursor.execute("""
            ALTER TABLE profile
            ADD COLUMN food_preferences TEXT DEFAULT ''
        """)

    if "food_restrictions" not in columns:
        cursor.execute("""
            ALTER TABLE profile
            ADD COLUMN food_restrictions TEXT DEFAULT ''
        """)

    if "usual_meals" not in columns:
        cursor.execute("""
            ALTER TABLE profile
            ADD COLUMN usual_meals TEXT DEFAULT ''
        """)

    if "main_difficulty" not in columns:
        cursor.execute("""
            ALTER TABLE profile
            ADD COLUMN main_difficulty TEXT DEFAULT ''
        """)

    if "updated_at" not in columns:
        cursor.execute("""
            ALTER TABLE profile
            ADD COLUMN updated_at TEXT DEFAULT ''
        """)

    conn.commit()
    conn.close()


init_database()
upgrade_database()


# =========================================================
# PROFILE FUNCTIONS
# =========================================================

def get_profile():

    conn = get_connection()

    df = pd.read_sql_query(
        "SELECT * FROM profile WHERE id = 1",
        conn
    )

    conn.close()

    if df.empty:
        return None

    return df.iloc[0].to_dict()


def save_profile(
    goal,
    age,
    height_cm,
    weight_kg,
    gender,
    activity_level,
    diet_type,
    food_preferences,
    food_restrictions,
    usual_meals,
    main_difficulty,
    calorie_target,
    protein_target
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO profile (
            id,
            goal,
            age,
            height_cm,
            weight_kg,
            gender,
            activity_level,
            diet_type,
            food_preferences,
            food_restrictions,
            usual_meals,
            main_difficulty,
            calorie_target,
            protein_target,
            created_at,
            updated_at
        )
        VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(id) DO UPDATE SET
            goal = excluded.goal,
            age = excluded.age,
            height_cm = excluded.height_cm,
            weight_kg = excluded.weight_kg,
            gender = excluded.gender,
            activity_level = excluded.activity_level,
            diet_type = excluded.diet_type,
            food_preferences = excluded.food_preferences,
            food_restrictions = excluded.food_restrictions,
            usual_meals = excluded.usual_meals,
            main_difficulty = excluded.main_difficulty,
            calorie_target = excluded.calorie_target,
            protein_target = excluded.protein_target,
            updated_at = CURRENT_TIMESTAMP
    """, (
        goal,
        age,
        height_cm,
        weight_kg,
        gender,
        activity_level,
        diet_type,
        food_preferences,
        food_restrictions,
        usual_meals,
        main_difficulty,
        calorie_target,
        protein_target
    ))

    conn.commit()
    conn.close()


# =========================================================
# MEAL FUNCTIONS
# =========================================================

def add_meal(
    meal_type,
    food_name,
    calories,
    protein,
    carbs,
    fat,
    portion,
    meal_date
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO meals (
            meal_type,
            food_name,
            calories,
            protein,
            carbs,
            fat,
            portion,
            meal_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        meal_type,
        food_name,
        calories,
        protein,
        carbs,
        fat,
        portion,
        str(meal_date)
    ))

    conn.commit()
    conn.close()


def delete_meal(meal_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM meals WHERE id = ?",
        (meal_id,)
    )

    conn.commit()
    conn.close()


def clear_date_meals(meal_date):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM meals WHERE meal_date = ?",
        (str(meal_date),)
    )

    conn.commit()
    conn.close()


def get_meals(meal_date):

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT *
        FROM meals
        WHERE meal_date = ?
        ORDER BY created_at DESC
        """,
        conn,
        params=(str(meal_date),)
    )

    conn.close()

    return df


def get_all_meals():

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT *
        FROM meals
        ORDER BY meal_date DESC, created_at DESC
        """,
        conn
    )

    conn.close()

    return df


# =========================================================
# TARGET CALCULATIONS
# =========================================================

def calculate_targets(profile):

    if not profile:
        return 2000, 80

    age = float(profile.get("age") or 0)
    height = float(profile.get("height_cm") or 0)
    weight = float(profile.get("weight_kg") or 0)
    gender = str(profile.get("gender") or "").lower()
    activity = str(profile.get("activity_level") or "")
    goal = str(profile.get("goal") or "")

    if age <= 0 or height <= 0 or weight <= 0:
        return 2000, 80

    # Mifflin-St Jeor estimate
    if gender == "male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    activity_factor = {
        "Sedentary": 1.20,
        "Lightly Active": 1.375,
        "Moderately Active": 1.55,
        "Very Active": 1.725
    }.get(activity, 1.20)

    calories = bmr * activity_factor

    if goal == "Fat Loss":
        calories -= 300

    elif goal == "Muscle Gain":
        calories += 250

    calories = max(1200, calories)

    # General practical protein estimate
    if goal == "Muscle Gain":
        protein = weight * 1.6
    elif goal == "Fat Loss":
        protein = weight * 1.5
    else:
        protein = weight * 1.2

    return round(calories), round(protein)


def get_targets(profile):

    calculated_calories, calculated_protein = calculate_targets(profile)

    if profile:

        custom_calories = profile.get("calorie_target") or 0
        custom_protein = profile.get("protein_target") or 0

        if custom_calories and custom_calories > 0:
            calculated_calories = custom_calories

        if custom_protein and custom_protein > 0:
            calculated_protein = custom_protein

    return calculated_calories, calculated_protein


# =========================================================
# TOTALS
# =========================================================

def get_daily_totals(df):

    if df.empty:
        return {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0
        }

    return {
        "calories": float(df["calories"].sum()),
        "protein": float(df["protein"].sum()),
        "carbs": float(df["carbs"].sum()),
        "fat": float(df["fat"].sum())
    }


def get_weekly_data():

    all_df = get_all_meals()

    if all_df.empty:
        return pd.DataFrame()

    all_df["meal_date"] = pd.to_datetime(
        all_df["meal_date"]
    )

    today = pd.Timestamp(date.today())
    start = today - pd.Timedelta(days=6)

    df = all_df[
        (all_df["meal_date"] >= start) &
        (all_df["meal_date"] <= today)
    ].copy()

    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby("meal_date").agg(
        calories=("calories", "sum"),
        protein=("protein", "sum"),
        carbs=("carbs", "sum"),
        fat=("fat", "sum")
    ).reset_index()

    return grouped


def get_monthly_data():

    all_df = get_all_meals()

    if all_df.empty:
        return pd.DataFrame()

    all_df["meal_date"] = pd.to_datetime(
        all_df["meal_date"]
    )

    today = pd.Timestamp(date.today())

    start = today.replace(day=1)

    df = all_df[
        (all_df["meal_date"] >= start) &
        (all_df["meal_date"] <= today)
    ].copy()

    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby("meal_date").agg(
        calories=("calories", "sum"),
        protein=("protein", "sum"),
        carbs=("carbs", "sum"),
        fat=("fat", "sum")
    ).reset_index()

    return grouped


# =========================================================
# GEMINI
# =========================================================

def get_gemini_client():

    try:
        api_key = st.secrets["GEMINI_API_KEY"]

        if not api_key:
            return None

        return genai.Client(api_key=api_key)

    except Exception:
        return None


def extract_json(text):

    if not text:
        return None

    text = text.strip()

    # Remove markdown fences
    text = re.sub(
        r"```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```\s*",
        "",
        text
    )

    # First direct attempt
    try:
        return json.loads(text)
    except Exception:
        pass

    # Find JSON object
    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if match:

        try:
            return json.loads(match.group())
        except Exception:
            pass

    return None


def clean_number(value):

    try:
        if isinstance(value, str):
            value = re.sub(
                r"[^0-9.\-]",
                "",
                value
            )

        return float(value)

    except Exception:
        return 0.0


def validate_food_result(data):

    if not isinstance(data, dict):
        return None

    return {
        "food_name": str(
            data.get("food_name", "Unknown food")
        ),

        "portion": str(
            data.get("portion", "1 serving")
        ),

        "calories": clean_number(
            data.get("calories", 0)
        ),

        "protein": clean_number(
            data.get("protein", 0)
        ),

        "carbs": clean_number(
            data.get("carbs", 0)
        ),

        "fat": clean_number(
            data.get("fat", 0)
        ),

        "confidence": str(
            data.get("confidence", "Medium")
        ),

        "notes": str(
            data.get("notes", "")
        )
    }


def analyze_food_image(uploaded_file):

    client = get_gemini_client()

    if client is None:
        return {
            "error":
            "Gemini API key is missing. Add GEMINI_API_KEY to Streamlit secrets."
        }

    image_bytes = uploaded_file.getvalue()

    prompt = """
You are a nutrition estimation assistant.

Analyze the food image.

Return ONLY valid JSON.

Use this exact structure:

{
  "food_name": "name of food",
  "portion": "estimated portion",
  "calories": 0,
  "protein": 0,
  "carbs": 0,
  "fat": 0,
  "confidence": "High/Medium/Low",
  "notes": "short explanation"
}

Rules:

- Estimate the visible serving.
- Calories and macros are estimates, not medical measurements.
- If multiple foods are visible, give a combined estimate.
- Do not invent extreme precision.
- Use grams for protein, carbs and fat.
"""

    for attempt in range(3):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
    types.Part.from_text(text=prompt),
    types.Part.from_bytes(
        data=image_bytes,
        mime_type=uploaded_file.type
    )
]
            )
            data = extract_json(
                getattr(response, "text", "")
            )

            result = validate_food_result(data)

            if result:
                return result

            return {
                "error":
                "The AI returned an unexpected result. Please try the image again."
            }

        except Exception as e:

            error_text = str(e).lower()

            if "503" in error_text or "unavailable" in error_text:

                if attempt < 2:
                    time.sleep(2)
                    continue

                return {
                    "error":
                    "The AI service is temporarily busy. Please try again in a moment."
                }

            if "404" in error_text or "not found" in error_text:

                return {
                    "error":
                    "The selected AI model is currently unavailable."
                }

            if "429" in error_text or "quota" in error_text:

                return {
                    "error":
                    "The AI usage limit has been reached. Please try again later."
                }

            if "timeout" in error_text:

                return {
                    "error":
                    "The AI request timed out. Please try again."
                }

            return {
                "error":
                "Food analysis failed. Please try another image."
            }

    return {
        "error":
        "Food analysis could not be completed."
    }


# =========================================================
# PROFILE COMPLETENESS
# =========================================================

def profile_complete(profile):

    if not profile:
        return False

    required = [
        "goal",
        "age",
        "height_cm",
        "weight_kg",
        "gender",
        "activity_level",
        "diet_type"
    ]

    for field in required:

        value = profile.get(field)

        if value in [None, "", 0, "0"]:
            return False

    return True


# =========================================================
# PERSONALIZED GUIDANCE
# =========================================================

def generate_guidance(
    profile,
    totals,
    calorie_target,
    protein_target
):

    if not profile:
        return [
            "Complete your profile to get personalized guidance.",
            "Start by logging your next meal."
        ]

    guidance = []

    calories = totals["calories"]
    protein = totals["protein"]

    goal = profile.get("goal", "")
    difficulty = profile.get(
        "main_difficulty",
        ""
    )

    remaining_calories = calorie_target - calories
    remaining_protein = protein_target - protein

    if remaining_protein > 20:

        guidance.append(
            f"You still need about {remaining_protein:.0f} g protein today."
        )

    elif remaining_protein > 0:

        guidance.append(
            f"You are close to your protein target — about {remaining_protein:.0f} g remaining."
        )

    else:

        guidance.append(
            "You have reached your protein target for today."
        )

    if remaining_calories > 500:

        guidance.append(
            f"You have roughly {remaining_calories:.0f} kcal remaining."
        )

    elif remaining_calories > 0:

        guidance.append(
            f"About {remaining_calories:.0f} kcal remain in your target."
        )

    else:

        guidance.append(
            "You have reached or crossed your estimated calorie target."
        )

    if goal == "Muscle Gain":

        guidance.append(
            "Prioritize a protein-rich meal or snack and regular strength training."
        )

    elif goal == "Fat Loss":

        guidance.append(
            "Focus on protein, vegetables, fibre and filling meals rather than simply eating less."
        )

    elif goal == "Maintenance":

        guidance.append(
            "Aim for consistent meals and keep your protein intake steady."
        )

    if difficulty:

        guidance.append(
            f"Your selected challenge is: {difficulty}. Use your meal log to identify patterns around it."
        )

    return guidance[:4]


# =========================================================
# MEAL RECOMMENDATIONS
# =========================================================

def meal_recommendations(
    profile,
    remaining_calories,
    remaining_protein
):

    diet = profile.get(
        "diet_type",
        "Vegetarian"
    ) if profile else "Vegetarian"

    preferences = (
        profile.get("food_preferences", "")
        if profile
        else ""
    )

    restrictions = (
        profile.get("food_restrictions", "")
        if profile
        else ""
    )

    suggestions = []

    if diet in ["Vegetarian", "Eggetarian", "Vegan"]:

        if remaining_protein >= 25:

            suggestions.extend([
                "Paneer/tofu bowl with vegetables",
                "Dal + curd/tofu + vegetables",
                "Chickpea or rajma salad"
            ])

        elif remaining_protein >= 10:

            suggestions.extend([
                "Sprouts chaat",
                "Greek yogurt/curd with seeds",
                "Paneer or tofu snack"
            ])

        else:

            suggestions.extend([
                "Fruit + nuts",
                "Vegetable soup",
                "Light salad with a protein source"
            ])

    else:

        if remaining_protein >= 25:

            suggestions.extend([
                "Egg + vegetable meal",
                "Chicken + vegetables",
                "Fish + vegetables"
            ])

        else:

            suggestions.extend([
                "Egg snack",
                "Chicken salad",
                "Light protein-rich meal"
            ])

    if remaining_calories < 250:

        suggestions = [
            item for item in suggestions
            if "bowl" not in item.lower()
        ]

    if preferences:

        suggestions.append(
            f"Preference to consider: {preferences}"
        )

    if restrictions:

        suggestions.append(
            f"Remember your restriction: {restrictions}"
        )

    return suggestions[:5]


# =========================================================
# WHATSAPP SUMMARY
# =========================================================

def create_whatsapp_summary(
    profile,
    totals,
    calorie_target,
    protein_target
):

    today_text = date.today().strftime(
        "%d %b %Y"
    )

    goal = (
        profile.get("goal", "Not set")
        if profile
        else "Not set"
    )

    remaining_calories = max(
        0,
        calorie_target - totals["calories"]
    )

    remaining_protein = max(
        0,
        protein_target - totals["protein"]
    )

    message = f"""
🥗 MacroSnap Daily Summary
📅 {today_text}

🎯 Goal: {goal}

🔥 Calories
{totals["calories"]:.0f} / {calorie_target:.0f} kcal

💪 Protein
{totals["protein"]:.1f} / {protein_target:.1f} g

🍞 Carbs
{totals["carbs"]:.1f} g

🥑 Fat
{totals["fat"]:.1f} g

📌 Remaining
Calories: {remaining_calories:.0f} kcal
Protein: {remaining_protein:.1f} g

Keep logging your meals in MacroSnap.
""".strip()

    return message


# =========================================================
# SESSION STATE
# =========================================================

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 1


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🥗 MacroSnap")

profile = get_profile()

if profile_complete(profile):

    st.sidebar.success("Profile ready ✓")

else:

    st.sidebar.warning(
        "Complete your profile"
    )


page_options = [
    "Dashboard",
    "Food Analyzer",
    "Meal History",
    "Weekly Insights",
    "Monthly Insights",
    "Profile & Targets",
    "Export Data"
]

page = st.sidebar.radio(
    "Navigate",
    page_options,
    index=page_options.index(
        st.session_state.page
    )
)

st.session_state.page = page

st.sidebar.divider()

selected_date = st.sidebar.date_input(
    "Meal date",
    value=date.today()
)

st.sidebar.divider()

st.sidebar.caption(
    "MacroSnap estimates nutrition from your meal log. "
    "AI food analysis is an estimate and should not be treated as medical advice."
)


# =========================================================
# PROFILE ONBOARDING
# =========================================================

if not profile_complete(profile) and page != "Profile & Targets":

    st.title("👋 Welcome to MacroSnap")

    st.write(
        "Let's set up your profile so MacroSnap can personalize "
        "your calorie, protein and meal guidance."
    )

    st.progress(
        st.session_state.onboarding_step / 4
    )

    step = st.session_state.onboarding_step

    if step == 1:

        st.subheader("Step 1 — Basic Information")

        age = st.number_input(
            "Age",
            min_value=10,
            max_value=100,
            value=20
        )

        gender = st.selectbox(
            "Gender",
            ["Female", "Male", "Prefer not to say"]
        )

        height = st.number_input(
            "Height (cm)",
            min_value=100.0,
            max_value=250.0,
            value=160.0
        )

        weight = st.number_input(
            "Weight (kg)",
            min_value=25.0,
            max_value=250.0,
            value=60.0
        )

        if st.button(
            "Next →",
            use_container_width=True
        ):

            st.session_state.onboarding_basic = {
                "age": age,
                "gender": gender,
                "height": height,
                "weight": weight
            }

            st.session_state.onboarding_step = 2
            st.rerun()

    elif step == 2:

        st.subheader("Step 2 — Your Goal")

        goal = st.selectbox(
            "Main goal",
            GOALS
        )

        activity = st.selectbox(
            "Activity level",
            ACTIVITY_LEVELS
        )

        diet = st.selectbox(
            "Diet type",
            DIET_TYPES
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "← Back",
                use_container_width=True
            ):

                st.session_state.onboarding_step = 1
                st.rerun()

        with col2:

            if st.button(
                "Next →",
                use_container_width=True
            ):

                st.session_state.onboarding_goal = {
                    "goal": goal,
                    "activity": activity,
                    "diet": diet
                }

                st.session_state.onboarding_step = 3
                st.rerun()

    elif step == 3:

        st.subheader("Step 3 — Personal Preferences")

        preferences = st.text_area(
            "Foods you like",
            placeholder="Example: paneer, dosa, fruits, dal..."
        )

        restrictions = st.text_area(
            "Foods you avoid / restrictions",
            placeholder="Example: peanuts, lactose..."
        )

        usual_meals = st.text_input(
            "Usual meal pattern",
            placeholder="Example: breakfast, lunch, evening snack, dinner"
        )

        difficulty = st.selectbox(
            "What is your main difficulty?",
            [
                "Staying consistent",
                "Getting enough protein",
                "Controlling portions",
                "Choosing healthy foods",
                "Tracking meals",
                "Late-night eating",
                "Other"
            ]
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "← Back",
                use_container_width=True
            ):

                st.session_state.onboarding_step = 2
                st.rerun()

        with col2:

            if st.button(
                "Next →",
                use_container_width=True
            ):

                st.session_state.onboarding_preferences = {
                    "preferences": preferences,
                    "restrictions": restrictions,
                    "usual_meals": usual_meals,
                    "difficulty": difficulty
                }

                st.session_state.onboarding_step = 4
                st.rerun()

    else:

        st.subheader("Step 4 — Review")

        basic = st.session_state.get(
            "onboarding_basic",
            {}
        )

        goal_data = st.session_state.get(
            "onboarding_goal",
            {}
        )

        pref_data = st.session_state.get(
            "onboarding_preferences",
            {}
        )

        st.write(
            f"**Age:** {basic.get('age', '')}"
        )

        st.write(
            f"**Height:** {basic.get('height', '')} cm"
        )

        st.write(
            f"**Weight:** {basic.get('weight', '')} kg"
        )

        st.write(
            f"**Goal:** {goal_data.get('goal', '')}"
        )

        st.write(
            f"**Activity:** {goal_data.get('activity', '')}"
        )

        st.write(
            f"**Diet:** {goal_data.get('diet', '')}"
        )

        st.write(
            f"**Main difficulty:** {pref_data.get('difficulty', '')}"
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "← Back",
                use_container_width=True
            ):

                st.session_state.onboarding_step = 3
                st.rerun()

        with col2:

            if st.button(
                "Save Profile ✓",
                use_container_width=True
            ):

                temp_profile = {
                    "age": basic.get("age"),
                    "height_cm": basic.get("height"),
                    "weight_kg": basic.get("weight")
                }

                calories, protein = calculate_targets(
                    {
                        **temp_profile,
                        "gender": goal_data.get(
                            "gender",
                            basic.get("gender")
                        ),
                        "activity_level": goal_data.get(
                            "activity"
                        ),
                        "goal": goal_data.get(
                            "goal"
                        )
                    }
                )

                save_profile(
                    goal_data.get("goal", ""),
                    basic.get("age", 0),
                    basic.get("height", 0),
                    basic.get("weight", 0),
                    basic.get("gender", ""),
                    goal_data.get("activity", ""),
                    goal_data.get("diet", ""),
                    pref_data.get("preferences", ""),
                    pref_data.get("restrictions", ""),
                    pref_data.get("usual_meals", ""),
                    pref_data.get("difficulty", ""),
                    calories,
                    protein
                )

                st.success(
                    "Profile saved successfully!"
                )

                st.session_state.onboarding_step = 1

                for key in [
                    "onboarding_basic",
                    "onboarding_goal",
                    "onboarding_preferences"
                ]:

                    if key in st.session_state:
                        del st.session_state[key]

                time.sleep(1)
                st.rerun()

    st.stop()


# =========================================================
# CURRENT PROFILE / TARGETS
# =========================================================

profile = get_profile()

calorie_target, protein_target = get_targets(
    profile
)


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.title("🏠 MacroSnap Dashboard")

    st.caption(
        f"Tracking for {selected_date.strftime('%d %B %Y')}"
    )

    today_df = get_meals(selected_date)

    totals = get_daily_totals(today_df)

    # -----------------------------------------------------
    # TOP METRICS
    # -----------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "🔥 Calories",
            f"{totals['calories']:.0f}",
            f"Target {calorie_target:.0f}"
        )

    with c2:

        st.metric(
            "💪 Protein",
            f"{totals['protein']:.1f} g",
            f"Target {protein_target:.1f} g"
        )

    with c3:

        st.metric(
            "🍞 Carbs",
            f"{totals['carbs']:.1f} g"
        )

    with c4:

        st.metric(
            "🥑 Fat",
            f"{totals['fat']:.1f} g"
        )

    st.divider()

    # -----------------------------------------------------
    # PROGRESS
    # -----------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:

        st.subheader("🔥 Calorie Progress")

        calorie_progress = min(
            totals["calories"] / calorie_target,
            1.0
        ) if calorie_target else 0

        st.progress(
            calorie_progress
        )

        st.write(
            f"{totals['calories']:.0f} / "
            f"{calorie_target:.0f} kcal"
        )

    with col2:

        st.subheader("💪 Protein Progress")

        protein_progress = min(
            totals["protein"] / protein_target,
            1.0
        ) if protein_target else 0

        st.progress(
            protein_progress
        )

        st.write(
            f"{totals['protein']:.1f} / "
            f"{protein_target:.1f} g"
        )

    st.divider()

    # -----------------------------------------------------
    # PERSONALIZED GUIDANCE
    # -----------------------------------------------------

    st.subheader("🧠 Your Guidance")

    guidance = generate_guidance(
        profile,
        totals,
        calorie_target,
        protein_target
    )

    for item in guidance:

        st.info(item)

    # -----------------------------------------------------
    # MEAL SUMMARY
    # -----------------------------------------------------

    st.subheader("🍽️ Meal Summary")

    if today_df.empty:

        st.info(
            "No meals logged for this date yet."
        )

    else:

        meal_summary = (
            today_df
            .groupby("meal_type")
            .agg(
                calories=("calories", "sum"),
                protein=("protein", "sum")
            )
            .reset_index()
        )

        st.dataframe(
            meal_summary,
            use_container_width=True,
            hide_index=True
        )

    # -----------------------------------------------------
    # NEXT MEAL IDEAS
    # -----------------------------------------------------

    st.subheader("💡 What could you eat next?")

    remaining_calories = (
        calorie_target - totals["calories"]
    )

    remaining_protein = (
        protein_target - totals["protein"]
    )

    suggestions = meal_recommendations(
        profile,
        remaining_calories,
        remaining_protein
    )

    for suggestion in suggestions:

        st.write(
            f"• {suggestion}"
        )

    # -----------------------------------------------------
    # WHATSAPP
    # -----------------------------------------------------

    st.divider()

    st.subheader("📱 WhatsApp-ready Summary")

    whatsapp = create_whatsapp_summary(
        profile,
        totals,
        calorie_target,
        protein_target
    )

    st.text_area(
        "Copy and send this:",
        whatsapp,
        height=260
    )


# =========================================================
# FOOD ANALYZER
# =========================================================

elif page == "Food Analyzer":

    st.title("📸 Food Analyzer")

    st.write(
        "Upload a food image and MacroSnap will estimate "
        "calories and macros."
    )

    meal_type = st.selectbox(
        "Meal Type",
        MEAL_TYPES
    )

    uploaded_file = st.file_uploader(
        "Upload food image",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ]
    )

    if uploaded_file:

        st.image(
            uploaded_file,
            caption="Your food",
            use_container_width=True
        )

        if st.button(
            "🔍 Analyze Food",
            type="primary",
            use_container_width=True
        ):

            with st.spinner(
                "Analyzing your food..."
            ):

                result = analyze_food_image(
                    uploaded_file
                )

            st.session_state.analysis_result = result

    result = st.session_state.analysis_result

    if result:

        if "error" in result:

            st.error(
                result["error"]
            )

        else:

            st.subheader(
                "✏️ Edit Analysis Before Saving"
            )

            food_name = st.text_input(
                "Food name",
                value=result["food_name"]
            )

            portion = st.text_input(
                "Portion",
                value=result["portion"]
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:

                calories = st.number_input(
                    "Calories",
                    min_value=0.0,
                    value=float(result["calories"]),
                    step=1.0
                )

            with c2:

                protein = st.number_input(
                    "Protein (g)",
                    min_value=0.0,
                    value=float(result["protein"]),
                    step=0.1
                )

            with c3:

                carbs = st.number_input(
                    "Carbs (g)",
                    min_value=0.0,
                    value=float(result["carbs"]),
                    step=0.1
                )

            with c4:

                fat = st.number_input(
                    "Fat (g)",
                    min_value=0.0,
                    value=float(result["fat"]),
                    step=0.1
                )

            st.caption(
                f"AI confidence: {result['confidence']}"
            )

            if result.get("notes"):

                st.info(
                    result["notes"]
                )

            if st.button(
                "💾 Save Meal",
                type="primary",
                use_container_width=True
            ):

                if not food_name.strip():

                    st.error(
                        "Please enter a food name."
                    )

                else:

                    add_meal(
                        meal_type,
                        food_name.strip(),
                        calories,
                        protein,
                        carbs,
                        fat,
                        portion,
                        selected_date
                    )

                    st.session_state.analysis_result = None

                    st.success(
                        "Meal saved successfully! 🎉"
                    )

                    time.sleep(1)

                    st.rerun()

            if st.button(
                "🗑️ Discard Analysis",
                use_container_width=True
            ):

                st.session_state.analysis_result = None
                st.rerun()


# =========================================================
# MEAL HISTORY
# =========================================================

elif page == "Meal History":

    st.title("📚 Meal History")

    all_meals = get_all_meals()

    if all_meals.empty:

        st.info(
            "No meals have been logged yet."
        )

    else:

        search = st.text_input(
            "🔎 Search food",
            placeholder="Example: paneer, dosa, salad..."
        )

        filter_meal = st.selectbox(
            "Filter by meal type",
            ["All"] + MEAL_TYPES
        )

        filtered = all_meals.copy()

        if search:

            filtered = filtered[
                filtered["food_name"]
                .str.contains(
                    search,
                    case=False,
                    na=False
                )
            ]

        if filter_meal != "All":

            filtered = filtered[
                filtered["meal_type"] == filter_meal
            ]

        display_df = filtered[
            [
                "id",
                "meal_date",
                "meal_type",
                "food_name",
                "portion",
                "calories",
                "protein",
                "carbs",
                "fat"
            ]
        ].copy()

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("Delete a Meal")

        if not filtered.empty:

            selected_id = st.selectbox(
                "Select meal ID",
                filtered["id"].tolist()
            )

            confirm_delete = st.checkbox(
                "I confirm that I want to delete this meal."
            )

            if st.button(
                "Delete Selected Meal",
                disabled=not confirm_delete
            ):

                delete_meal(
                    selected_id
                )

                st.success(
                    "Meal deleted."
                )

                time.sleep(0.7)
                st.rerun()

        st.divider()

        st.subheader(
            f"Clear all meals for {selected_date.strftime('%d %B %Y')}"
        )

        confirm_clear = st.checkbox(
            "I understand that this will remove all meals for this date."
        )

        if st.button(
            "🗑️ Clear Selected Date",
            disabled=not confirm_clear
        ):

            clear_date_meals(
                selected_date
            )

            st.success(
                "Meals cleared for the selected date."
            )

            time.sleep(0.7)
            st.rerun()


# =========================================================
# WEEKLY INSIGHTS
# =========================================================

elif page == "Weekly Insights":

    st.title("📊 Weekly Insights")

    weekly = get_weekly_data()

    if weekly.empty:

        st.info(
            "Log meals for a few days to see weekly insights."
        )

    else:

        weekly["meal_date"] = pd.to_datetime(
            weekly["meal_date"]
        )

        average_calories = weekly[
            "calories"
        ].mean()

        average_protein = weekly[
            "protein"
        ].mean()

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Average Calories",
                f"{average_calories:.0f}"
            )

        with c2:

            st.metric(
                "Average Protein",
                f"{average_protein:.1f} g"
            )

        with c3:

            st.metric(
                "Days Logged",
                len(weekly)
            )

        st.divider()

        st.subheader(
            "📈 Calories — Last 7 Days"
        )

        chart_data = weekly.set_index(
            "meal_date"
        )[["calories"]]

        st.line_chart(
            chart_data
        )

        st.subheader(
            "💪 Protein — Last 7 Days"
        )

        protein_chart = weekly.set_index(
            "meal_date"
        )[["protein"]]

        st.line_chart(
            protein_chart
        )

        st.subheader(
            "📋 Weekly Summary"
        )

        st.dataframe(
            weekly,
            use_container_width=True,
            hide_index=True
        )

        # -------------------------------------------------
        # SMART WEEKLY COACH
        # -------------------------------------------------

        st.divider()

        st.subheader(
            "🧠 Smart Weekly Coach"
        )

        if profile:

            target_calories, target_protein = get_targets(
                profile
            )

            avg_calorie_difference = (
                average_calories -
                target_calories
            )

            avg_protein_difference = (
                average_protein -
                target_protein
            )

            if avg_protein_difference < -10:

                st.warning(
                    f"Your average protein was about "
                    f"{abs(avg_protein_difference):.0f} g below "
                    f"your target."
                )

                st.write(
                    "Try adding one protein-rich item to your regular meals."
                )

            elif avg_protein_difference >= 0:

                st.success(
                    "Your average protein intake was around or above your target."
                )

            if avg_calorie_difference > 300:

                st.info(
                    "Your average calorie intake was above your current estimated target."
                )

            elif avg_calorie_difference < -500:

                st.info(
                    "Your average calorie intake was considerably below your current estimated target."
                )

            else:

                st.write(
                    "Your average calorie intake was reasonably close to your current target."
                )

            st.markdown(
                "### Questions for next week"
            )

            questions = [
                "Which meal was easiest for you to keep consistent?",
                "Which meal usually caused you to miss your protein target?",
                "Were your portion sizes consistent?",
                "What is one small food habit you can improve next week?"
            ]

            for question in questions:

                st.write(
                    f"• {question}"
                )

        # -------------------------------------------------
        # WHATSAPP WEEKLY SUMMARY
        # -------------------------------------------------

        st.divider()

        st.subheader(
            "📱 WhatsApp-ready Weekly Summary"
        )

        days_logged = len(weekly)

        weekly_message = f"""
📊 MacroSnap Weekly Summary

📅 Last 7 days

🔥 Average Calories:
{average_calories:.0f} kcal/day

💪 Average Protein:
{average_protein:.1f} g/day

📅 Days Logged:
{days_logged}/7

🎯 Daily Targets:
Calories: {calorie_target:.0f} kcal
Protein: {protein_target:.1f} g

Keep tracking and improve one small habit next week. 💪
""".strip()

        st.text_area(
            "Copy this message:",
            weekly_message,
            height=250
        )


# =========================================================
# MONTHLY INSIGHTS
# =========================================================

elif page == "Monthly Insights":

    st.title("📅 Monthly Insights")

    monthly = get_monthly_data()

    if monthly.empty:

        st.info(
            "Log meals this month to see your monthly insights."
        )

    else:

        avg_calories = monthly[
            "calories"
        ].mean()

        avg_protein = monthly[
            "protein"
        ].mean()

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Average Calories",
                f"{avg_calories:.0f}"
            )

        with c2:

            st.metric(
                "Average Protein",
                f"{avg_protein:.1f} g"
            )

        with c3:

            st.metric(
                "Days Logged",
                len(monthly)
            )

        st.divider()

        st.subheader(
            "🔥 Monthly Calories"
        )

        st.line_chart(
            monthly.set_index(
                "meal_date"
            )[["calories"]]
        )

        st.subheader(
            "💪 Monthly Protein"
        )

        st.line_chart(
            monthly.set_index(
                "meal_date"
            )[["protein"]]
        )

        st.subheader(
            "📋 Monthly Data"
        )

        st.dataframe(
            monthly,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# PROFILE & TARGETS
# =========================================================

elif page == "Profile & Targets":

    st.title("👤 Profile & Targets")

    profile = get_profile()

    if not profile:

        st.warning(
            "No profile found."
        )

    else:

        with st.form(
            "profile_form"
        ):

            st.subheader(
                "Personal Information"
            )

            c1, c2 = st.columns(2)

            with c1:

                age = st.number_input(
                    "Age",
                    min_value=10,
                    max_value=100,
                    value=int(
                        profile.get("age") or 20
                    )
                )

                height = st.number_input(
                    "Height (cm)",
                    min_value=100.0,
                    max_value=250.0,
                    value=float(
                        profile.get("height_cm") or 160
                    )
                )

                weight = st.number_input(
                    "Weight (kg)",
                    min_value=25.0,
                    max_value=250.0,
                    value=float(
                        profile.get("weight_kg") or 60
                    )
                )

            with c2:

                gender_options = [
                    "Female",
                    "Male",
                    "Prefer not to say"
                ]

                saved_gender = profile.get(
                    "gender",
                    "Female"
                )

                gender_index = (
                    gender_options.index(
                        saved_gender
                    )
                    if saved_gender in gender_options
                    else 0
                )

                gender = st.selectbox(
                    "Gender",
                    gender_options,
                    index=gender_index
                )

                goal = st.selectbox(
                    "Goal",
                    GOALS,
                    index=(
                        GOALS.index(
                            profile.get(
                                "goal",
                                GOALS[0]
                            )
                        )
                        if profile.get(
                            "goal"
                        ) in GOALS
                        else 0
                    )
                )

                activity = st.selectbox(
                    "Activity Level",
                    ACTIVITY_LEVELS,
                    index=(
                        ACTIVITY_LEVELS.index(
                            profile.get(
                                "activity_level",
                                ACTIVITY_LEVELS[0]
                            )
                        )
                        if profile.get(
                            "activity_level"
                        ) in ACTIVITY_LEVELS
                        else 0
                    )
                )

            diet = st.selectbox(
                "Diet Type",
                DIET_TYPES,
                index=(
                    DIET_TYPES.index(
                        profile.get(
                            "diet_type",
                            DIET_TYPES[0]
                        )
                    )
                    if profile.get(
                        "diet_type"
                    ) in DIET_TYPES
                    else 0
                )
            )

            st.subheader(
                "Preferences"
            )

            preferences = st.text_area(
                "Foods you like",
                value=profile.get(
                    "food_preferences",
                    ""
                )
            )

            restrictions = st.text_area(
                "Foods you avoid / restrictions",
                value=profile.get(
                    "food_restrictions",
                    ""
                )
            )

            usual_meals = st.text_input(
                "Usual meals",
                value=profile.get(
                    "usual_meals",
                    ""
                )
            )

            difficulty_options = [
                "Staying consistent",
                "Getting enough protein",
                "Controlling portions",
                "Choosing healthy foods",
                "Tracking meals",
                "Late-night eating",
                "Other"
            ]

            saved_difficulty = profile.get(
                "main_difficulty",
                difficulty_options[0]
            )

            difficulty_index = (
                difficulty_options.index(
                    saved_difficulty
                )
                if saved_difficulty in difficulty_options
                else 0
            )

            difficulty = st.selectbox(
                "Main difficulty",
                difficulty_options,
                index=difficulty_index
            )

            st.subheader(
                "🎯 Nutrition Targets"
            )

            auto_calories, auto_protein = calculate_targets(
                {
                    "age": age,
                    "height_cm": height,
                    "weight_kg": weight,
                    "gender": gender,
                    "activity_level": activity,
                    "goal": goal
                }
            )

            st.info(
                f"Estimated targets: "
                f"{auto_calories:.0f} kcal/day and "
                f"{auto_protein:.0f} g protein/day"
            )

            calorie_override = st.number_input(
                "Custom calorie target (0 = use estimate)",
                min_value=0.0,
                value=float(
                    profile.get(
                        "calorie_target"
                    ) or 0
                ),
                step=50.0
            )

            protein_override = st.number_input(
                "Custom protein target (0 = use estimate)",
                min_value=0.0,
                value=float(
                    profile.get(
                        "protein_target"
                    ) or 0
                ),
                step=5.0
            )

            save = st.form_submit_button(
                "💾 Save Changes",
                use_container_width=True
            )

            if save:

                save_profile(
                    goal,
                    age,
                    height,
                    weight,
                    gender,
                    activity,
                    diet,
                    preferences,
                    restrictions,
                    usual_meals,
                    difficulty,
                    calorie_override,
                    protein_override
                )

                st.success(
                    "Profile updated successfully!"
                )

                time.sleep(0.8)
                st.rerun()

        st.divider()

        st.subheader(
            "Current Targets"
        )

        current_calories, current_protein = get_targets(
            get_profile()
        )

        c1, c2 = st.columns(2)

        with c1:

            st.metric(
                "Daily Calories",
                f"{current_calories:.0f} kcal"
            )

        with c2:

            st.metric(
                "Daily Protein",
                f"{current_protein:.1f} g"
            )


# =========================================================
# EXPORT DATA
# =========================================================

elif page == "Export Data":

    st.title("📤 Export Your Data")

    all_data = get_all_meals()

    if all_data.empty:

        st.info(
            "There is no meal data to export yet."
        )

    else:

        st.subheader(
            "CSV Export"
        )

        csv_data = all_data.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download CSV",
            data=csv_data,
            file_name="macrosnap_meals.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.divider()

        st.subheader(
            "Excel Export"
        )

        excel_buffer = BytesIO()

        with pd.ExcelWriter(
            excel_buffer,
            engine="openpyxl"
        ) as writer:

            all_data.to_excel(
                writer,
                index=False,
                sheet_name="Meals"
            )

            if profile:

                profile_df = pd.DataFrame(
                    [profile]
                )

                profile_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Profile"
                )

        st.download_button(
            "⬇️ Download Excel",
            data=excel_buffer.getvalue(),
            file_name="macrosnap_data.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True
        )

        st.divider()

        st.subheader(
            "Data Preview"
        )

        st.dataframe(
            all_data,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "🥗 MacroSnap • Personal nutrition tracking dashboard"
)

st.caption(
    "Nutrition values and AI image analysis are estimates. "
    "They are not a substitute for professional medical or dietary advice."
)
