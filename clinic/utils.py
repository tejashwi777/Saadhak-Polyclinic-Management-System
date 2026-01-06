# clinic/utils.py
import heapq
from datetime import datetime, timedelta
from .models import Appointment, Schedule


def calculate_urgency_score(reason):
    score = 0
    keywords = ['emergency', 'pain', 'urgent', 'severe', 'fever', 'bleeding', 'accident']
    reason_lower = reason.lower()
    for word in keywords:
        if word in reason_lower:
            score += 30
    return score

def smart_schedule_appointment(appointment):
    """
    Smart scheduling using priority queue (heapq)
    Factors: urgency + waiting time + doctor availability
    """
    try:
        # Get doctor's schedule for the requested day
        day_name = appointment.date.strftime('%A')  # e.g., Monday
        schedule = Schedule.objects.filter(
            doctor=appointment.doctor,
            day=day_name
        ).first()

        if not schedule:
            return False

        # Define working hours
        start_time = datetime.combine(appointment.date, schedule.start_time)
        end_time = datetime.combine(appointment.date, schedule.end_time)
        slot_duration = timedelta(minutes=schedule.slot_duration or 30)

        # Get already booked slots on that date
        booked_times = Appointment.objects.filter(
            doctor=appointment.doctor,
            date=appointment.date
        ).values_list('time', flat=True)

        # Generate available time slots
        available_slots = []
        current = start_time
        while current < end_time:
            if current.time() not in booked_times:
                priority = 0
                # Higher priority for urgent cases
                urgency = calculate_urgency_score(appointment.reason)
                priority -= urgency  # heapq is min-heap, so negative
                heapq.heappush(available_slots, (priority, current.time()))
            current += slot_duration

        if available_slots:
            # Assign the highest priority (lowest number) slot
            _, best_time = heapq.heappop(available_slots)
            appointment.time = best_time
            appointment.urgency_score = calculate_urgency_score(appointment.reason)
            appointment.save()
            return True
        else:
            return False

    except Exception as e:
        print(f"Scheduling error: {e}")
        return False