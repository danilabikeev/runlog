# -*- coding: utf-8 -*-
"""
RunLog — дневник тренировок для бега.
Запуск: python app.py
Затем открыть на телефоне (в той же Wi-Fi сети): http://<IP-компьютера>:5000
"""
import json
from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from models import db, Race, PlanWorkout, WorkoutResult, GpsTrack
from plan_generator import generate_plan, WORKOUT_TYPES
from gpx_import import parse_track_file

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///runlog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "runlog-secret-key-change-me"

db.init_app(app)

with app.app_context():
    db.create_all()


# ---------- Вспомогательные функции ----------

def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def hms_to_sec(h, m, s):
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)


# ---------- Главная / дашборд ----------

@app.route("/")
def index():
    today = date.today()
    next_race = Race.query.filter(Race.race_date >= today).order_by(Race.race_date.asc()).first()

    upcoming = (
        PlanWorkout.query.filter(PlanWorkout.workout_date >= today, PlanWorkout.is_done == False)
        .order_by(PlanWorkout.workout_date.asc())
        .limit(5)
        .all()
    )
    recent_results = (
        WorkoutResult.query.order_by(WorkoutResult.result_date.desc(), WorkoutResult.id.desc())
        .limit(5)
        .all()
    )

    # статистика за последние 7 и 30 дней
    from datetime import timedelta
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    week_results = WorkoutResult.query.filter(WorkoutResult.result_date >= week_ago).all()
    month_results = WorkoutResult.query.filter(WorkoutResult.result_date >= month_ago).all()

    week_km = round(sum(r.distance_km for r in week_results), 1)
    month_km = round(sum(r.distance_km for r in month_results), 1)

    return render_template(
        "index.html",
        next_race=next_race,
        upcoming=upcoming,
        recent_results=recent_results,
        week_km=week_km,
        month_km=month_km,
        workout_types=WORKOUT_TYPES,
    )


# ---------- Соревнования и генерация плана ----------

@app.route("/races")
def races_list():
    races = Race.query.order_by(Race.race_date.asc()).all()
    return render_template("races.html", races=races)


@app.route("/races/new", methods=["GET", "POST"])
def race_new():
    if request.method == "POST":
        name = request.form["name"].strip()
        race_date = parse_date(request.form["race_date"])
        distance_km = float(request.form["distance_km"])
        goal_h = request.form.get("goal_h", "")
        goal_m = request.form.get("goal_m", "")
        goal_s = request.form.get("goal_s", "")
        goal_time_sec = None
        if goal_h or goal_m or goal_s:
            goal_time_sec = hms_to_sec(goal_h, goal_m, goal_s)
        notes = request.form.get("notes", "").strip()

        race = Race(
            name=name,
            race_date=race_date,
            distance_km=distance_km,
            goal_time_sec=goal_time_sec,
            notes=notes,
        )
        db.session.add(race)
        db.session.commit()

        if request.form.get("generate_plan") == "on":
            workouts = generate_plan(distance_km, race_date)
            for w in workouts:
                pw = PlanWorkout(
                    race_id=race.id,
                    workout_date=w["workout_date"],
                    workout_type=w["workout_type"],
                    title=w["title"],
                    description=w["description"],
                    target_distance_km=w["target_distance_km"],
                    target_duration_min=w["target_duration_min"],
                )
                db.session.add(pw)
            db.session.commit()
            flash(f'План тренировок к «{name}» создан ({len(workouts)} тренировок).', "success")
        else:
            flash(f'Соревнование «{name}» добавлено.', "success")

        return redirect(url_for("races_list"))

    return render_template("race_form.html")


@app.route("/races/<int:race_id>/delete", methods=["POST"])
def race_delete(race_id):
    race = Race.query.get_or_404(race_id)
    db.session.delete(race)
    db.session.commit()
    flash("Соревнование и его план удалены.", "info")
    return redirect(url_for("races_list"))


# ---------- План тренировок ----------

@app.route("/plan")
def plan_view():
    race_id = request.args.get("race_id", type=int)
    query = PlanWorkout.query
    if race_id:
        query = query.filter_by(race_id=race_id)
    workouts = query.order_by(PlanWorkout.workout_date.asc()).all()

    races = Race.query.order_by(Race.race_date.asc()).all()
    return render_template(
        "plan.html", workouts=workouts, races=races,
        selected_race_id=race_id, workout_types=WORKOUT_TYPES, today=date.today()
    )


@app.route("/plan/new", methods=["GET", "POST"])
def plan_new():
    races = Race.query.order_by(Race.race_date.asc()).all()
    if request.method == "POST":
        pw = PlanWorkout(
            race_id=request.form.get("race_id") or None,
            workout_date=parse_date(request.form["workout_date"]),
            workout_type=request.form["workout_type"],
            title=request.form["title"].strip(),
            description=request.form.get("description", "").strip(),
            target_distance_km=float(request.form["target_distance_km"]) if request.form.get("target_distance_km") else None,
            target_duration_min=int(request.form["target_duration_min"]) if request.form.get("target_duration_min") else None,
        )
        db.session.add(pw)
        db.session.commit()
        flash("Тренировка добавлена в план.", "success")
        return redirect(url_for("plan_view"))
    return render_template("plan_form.html", races=races, workout_types=WORKOUT_TYPES)


@app.route("/plan/<int:workout_id>/toggle_done", methods=["POST"])
def plan_toggle_done(workout_id):
    pw = PlanWorkout.query.get_or_404(workout_id)
    pw.is_done = not pw.is_done
    db.session.commit()
    return jsonify({"ok": True, "is_done": pw.is_done})


@app.route("/plan/<int:workout_id>/delete", methods=["POST"])
def plan_delete(workout_id):
    pw = PlanWorkout.query.get_or_404(workout_id)
    db.session.delete(pw)
    db.session.commit()
    flash("Тренировка удалена из плана.", "info")
    return redirect(url_for("plan_view"))


# ---------- Результаты (ручной ввод) ----------

@app.route("/results")
def results_list():
    results = WorkoutResult.query.order_by(
        WorkoutResult.result_date.desc(), WorkoutResult.id.desc()
    ).all()
    return render_template("results.html", results=results)


@app.route("/results/new", methods=["GET", "POST"])
def result_new():
    today = date.today()
    open_plan_workouts = (
        PlanWorkout.query.filter(PlanWorkout.is_done == False)
        .order_by(PlanWorkout.workout_date.asc())
        .all()
    )
    if request.method == "POST":
        h = request.form.get("dur_h", "0")
        m = request.form.get("dur_m", "0")
        s = request.form.get("dur_s", "0")
        duration_sec = hms_to_sec(h, m, s)

        result = WorkoutResult(
            plan_workout_id=request.form.get("plan_workout_id") or None,
            result_date=parse_date(request.form["result_date"]),
            distance_km=float(request.form["distance_km"]),
            duration_sec=duration_sec,
            avg_hr=int(request.form["avg_hr"]) if request.form.get("avg_hr") else None,
            perceived_effort=int(request.form["perceived_effort"]) if request.form.get("perceived_effort") else None,
            notes=request.form.get("notes", "").strip(),
            source="manual",
        )
        db.session.add(result)

        if result.plan_workout_id:
            pw = PlanWorkout.query.get(result.plan_workout_id)
            if pw:
                pw.is_done = True

        db.session.commit()
        flash("Результат тренировки сохранён.", "success")
        return redirect(url_for("results_list"))

    return render_template("result_form.html", today=today, open_plan_workouts=open_plan_workouts)


@app.route("/results/<int:result_id>/delete", methods=["POST"])
def result_delete(result_id):
    r = WorkoutResult.query.get_or_404(result_id)
    db.session.delete(r)
    db.session.commit()
    flash("Результат удалён.", "info")
    return redirect(url_for("results_list"))


@app.route("/results/<int:result_id>")
def result_detail(result_id):
    r = WorkoutResult.query.get_or_404(result_id)
    track_points = []
    if r.gps_track:
        track_points = json.loads(r.gps_track.points_json)
    return render_template("result_detail.html", r=r, track_points=track_points)


# ---------- GPS-трекер (live-запись через браузер телефона) ----------

@app.route("/tracker")
def tracker():
    open_plan_workouts = (
        PlanWorkout.query.filter(PlanWorkout.is_done == False, PlanWorkout.workout_type != "rest")
        .order_by(PlanWorkout.workout_date.asc())
        .all()
    )
    return render_template("tracker.html", open_plan_workouts=open_plan_workouts)


@app.route("/tracker/import", methods=["GET", "POST"])
def tracker_import():
    """Импорт трека, записанного смарт-часами (GPX/TCX), как результат тренировки."""
    open_plan_workouts = (
        PlanWorkout.query.filter(PlanWorkout.is_done == False, PlanWorkout.workout_type != "rest")
        .order_by(PlanWorkout.workout_date.asc())
        .all()
    )
    if request.method == "POST":
        file = request.files.get("track_file")
        if not file or file.filename == "":
            flash("Выберите файл GPX или TCX, экспортированный с часов.", "error")
            return redirect(url_for("tracker_import"))

        try:
            distance_km, duration_sec, points = parse_track_file(file.filename, file.read())
        except Exception as e:
            flash(f"Не удалось прочитать файл: {e}", "error")
            return redirect(url_for("tracker_import"))

        if distance_km == 0 or duration_sec == 0:
            flash("В файле не найдено точек трека или отметок времени.", "error")
            return redirect(url_for("tracker_import"))

        result_date_str = request.form.get("result_date")
        result_date = parse_date(result_date_str) if result_date_str else date.today()
        plan_workout_id = request.form.get("plan_workout_id") or None

        result = WorkoutResult(
            plan_workout_id=plan_workout_id,
            result_date=result_date,
            distance_km=distance_km,
            duration_sec=duration_sec,
            source="watch",
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(result)
        db.session.flush()

        track = GpsTrack(result_id=result.id, points_json=json.dumps(points))
        db.session.add(track)

        if plan_workout_id:
            pw = PlanWorkout.query.get(plan_workout_id)
            if pw:
                pw.is_done = True

        db.session.commit()
        flash(f"Трек с часов импортирован: {distance_km} км за {duration_sec // 60} мин.", "success")
        return redirect(url_for("result_detail", result_id=result.id))

    return render_template("tracker_import.html", open_plan_workouts=open_plan_workouts, today=date.today())


@app.route("/api/tracker/save", methods=["POST"])
def tracker_save():
    """Принимает записанный GPS-трек с телефона и сохраняет как результат тренировки."""
    data = request.get_json(force=True)

    points = data.get("points", [])
    distance_km = float(data.get("distance_km", 0))
    duration_sec = int(data.get("duration_sec", 0))
    plan_workout_id = data.get("plan_workout_id") or None

    result = WorkoutResult(
        plan_workout_id=plan_workout_id,
        result_date=date.today(),
        distance_km=round(distance_km, 3),
        duration_sec=duration_sec,
        source="gps",
        notes=data.get("notes", ""),
    )
    db.session.add(result)
    db.session.flush()  # получить result.id до commit

    track = GpsTrack(result_id=result.id, points_json=json.dumps(points))
    db.session.add(track)

    if plan_workout_id:
        pw = PlanWorkout.query.get(plan_workout_id)
        if pw:
            pw.is_done = True

    db.session.commit()
    return jsonify({"ok": True, "result_id": result.id})


# ---------- Статистика ----------

@app.route("/stats")
def stats():
    results = WorkoutResult.query.order_by(WorkoutResult.result_date.asc()).all()
    total_km = round(sum(r.distance_km for r in results), 1)
    total_runs = len(results)
    total_sec = sum(r.duration_sec for r in results)

    # данные для графика по неделям (последние 12 недель)
    from collections import defaultdict
    from datetime import timedelta
    weekly = defaultdict(float)
    for r in results:
        monday = r.result_date - timedelta(days=r.result_date.weekday())
        weekly[monday] += r.distance_km

    sorted_weeks = sorted(weekly.items())[-12:]
    chart_labels = [d.strftime("%d.%m") for d, _ in sorted_weeks]
    chart_values = [round(v, 1) for _, v in sorted_weeks]

    return render_template(
        "stats.html",
        total_km=total_km,
        total_runs=total_runs,
        total_sec=total_sec,
        chart_labels=json.dumps(chart_labels),
        chart_values=json.dumps(chart_values),
    )


# ---------- PWA: manifest и service worker ----------

@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")


@app.route("/service-worker.js")
def service_worker():
    return app.send_static_file("service-worker.js")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)