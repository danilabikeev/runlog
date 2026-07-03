# plan_generator.py
from datetime import date, timedelta
from typing import List, Dict, Any

WORKOUT_TYPES = {
    'easy': 'Лёгкая',
    'tempo': 'Темповая',
    'intervals': 'Интервальная',
    'long': 'Длинная',
    'rest': 'Отдых'
}

def generate_plan(race_distance_km: float, race_date: date) -> List[Dict[str, Any]]:
    today = date.today()
    days_until_race = (race_date - today).days

    if days_until_race < 14:
        return []

    weeks = min(days_until_race // 7, 8)
    plan = []
    current_date = today

    for week in range(weeks):
        week_days = {
            0: ('easy', 'Лёгкая пробежка', 5),
            1: ('tempo', 'Темповая работа', 6),
            2: ('easy', 'Лёгкая пробежка', 5),
            3: ('intervals', 'Интервалы', 7),
            4: ('long', 'Длинная пробежка', 12),
        }
        
        if week == weeks - 1:
            week_days = {
                0: ('easy', 'Лёгкая пробежка', 4),
                1: ('tempo', 'Темповая работа', 5),
                2: ('easy', 'Лёгкая', 3),
                3: ('easy', 'Лёгкая', 3),
                4: ('rest', 'Отдых перед стартом', 0),
            }

        for day_offset, (wtype, title, base_km) in week_days.items():
            if wtype == 'rest':
                continue
            workout_date = current_date + timedelta(days=day_offset)
            if workout_date > race_date:
                continue
            multiplier = 1 + 0.05 * week
            distance = round(base_km * multiplier, 1)
            plan.append({
                'workout_date': workout_date,
                'workout_type': wtype,
                'title': title,
                'description': f'Дистанция: {distance} км' if wtype != 'intervals' else 'Интервалы 6×800 м',
                'target_distance_km': distance if wtype != 'intervals' else None,
                'target_duration_min': None,
            })

        current_date += timedelta(days=7)

    return plan