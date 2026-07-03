# models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Race(db.Model):
    __tablename__ = 'races'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    race_date = db.Column(db.Date, nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    goal_time_sec = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    workouts = db.relationship('PlanWorkout', backref='race', lazy='dynamic')

    def goal_time_str(self):
        if self.goal_time_sec is None:
            return '—'
        h = self.goal_time_sec // 3600
        m = (self.goal_time_sec % 3600) // 60
        s = self.goal_time_sec % 60
        return f'{h:02d}:{m:02d}:{s:02d}'


class PlanWorkout(db.Model):
    __tablename__ = 'plan_workouts'
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('races.id'), nullable=True)
    workout_date = db.Column(db.Date, nullable=False)
    workout_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    target_distance_km = db.Column(db.Float, nullable=True)
    target_duration_min = db.Column(db.Integer, nullable=True)
    is_done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkoutResult(db.Model):
    __tablename__ = 'workout_results'
    id = db.Column(db.Integer, primary_key=True)
    plan_workout_id = db.Column(db.Integer, db.ForeignKey('plan_workouts.id'), nullable=True)
    result_date = db.Column(db.Date, nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    duration_sec = db.Column(db.Integer, nullable=False)
    avg_hr = db.Column(db.Integer, nullable=True)
    perceived_effort = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, default='')
    source = db.Column(db.String(20), default='manual')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    gps_track = db.relationship('GpsTrack', backref='result', uselist=False)
    plan_workout = db.relationship('PlanWorkout', backref='results')


class GpsTrack(db.Model):
    __tablename__ = 'gps_tracks'
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('workout_results.id'), unique=True)
    points_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)