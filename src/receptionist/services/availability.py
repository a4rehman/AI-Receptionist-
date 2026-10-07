from datetime import datetime, timedelta, date, time
from typing import Optional
import pytz
from sqlalchemy import select, and_, or_
from receptionist.db.models import (
    Appointment, AppointmentStatus, StaffSchedule, StaffService,
    Service, Holiday, BusinessHours, Staff,
)
from receptionist.utils.datetime_utils import time_to_minutes, minutes_to_time


class AvailabilityService:
    def __init__(self, session):
        self.session = session

    async def get_available_slots(
        self,
        tenant_id: str,
        service_id: str,
        target_date: date,
        staff_id: Optional[str] = None,
        timezone: str = "UTC",
        duration_minutes: Optional[int] = None,
        buffer_minutes: int = 0,
    ) -> list[dict]:
        service_result = await self.session.execute(
            select(Service).where(Service.id == service_id, Service.tenant_id == tenant_id)
        )
        service = service_result.scalar_one_or_none()
        if not service:
            return []

        duration = duration_minutes or service.duration_minutes

        if staff_id:
            staff_result = await self.session.execute(
                select(Staff).where(Staff.id == staff_id, Staff.tenant_id == tenant_id)
            )
            staff = staff_result.scalar_one_or_none()
            if not staff:
                return []
            staff_ids = [staff_id]
        else:
            staff_services_result = await self.session.execute(
                select(StaffService.staff_id).where(StaffService.service_id == service_id)
            )
            staff_ids = [row[0] for row in staff_services_result.fetchall()]

        if not staff_ids:
            return []

        holiday_result = await self.session.execute(
            select(Holiday).where(Holiday.tenant_id == tenant_id, Holiday.date == target_date.isoformat())
        )
        if holiday_result.scalar_one_or_none():
            return []

        day_of_week = target_date.weekday()
        schedule_result = await self.session.execute(
            select(StaffSchedule).where(
                StaffSchedule.staff_id.in_(staff_ids),
                StaffSchedule.day_of_week == day_of_week,
                StaffSchedule.is_active == True,
            )
        )
        schedules = schedule_result.scalars().all()
        if not schedules:
            return []

        business_hours_result = await self.session.execute(
            select(BusinessHours).where(
                BusinessHours.tenant_id == tenant_id,
                BusinessHours.day_of_week == day_of_week,
                BusinessHours.is_closed == False,
            )
        )
        biz_hours = business_hours_result.scalar_one_or_none()
        if not biz_hours:
            return []

        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        all_slots = []

        for schedule in schedules:
            slot_start = max(time_to_minutes(schedule.start_time), time_to_minutes(biz_hours.start_time))
            slot_end = min(time_to_minutes(schedule.end_time), time_to_minutes(biz_hours.end_time))

            current = slot_start
            while current + duration <= slot_end:
                slot_time = minutes_to_time(current)
                slot_end_time = minutes_to_time(current + duration)

                if target_date == now.date():
                    slot_dt = tz.localize(datetime.combine(target_date, time(current // 60, current % 60)))
                    if slot_dt <= now + timedelta(minutes=30):
                        current += duration + buffer_minutes
                        continue

                is_available = await self._check_slot_available(
                    tenant_id, staff_ids, target_date, slot_time, slot_end_time, duration
                )
                if is_available:
                    staff_result = await self.session.execute(
                        select(Staff).where(Staff.id == schedule.staff_id)
                    )
                    staff = staff_result.scalar_one_or_none()
                    all_slots.append({
                        "start_time": slot_time,
                        "end_time": slot_end_time,
                        "staff_id": schedule.staff_id,
                        "staff_name": staff.name if staff else None,
                    })

                current += duration + buffer_minutes

        return all_slots

    async def _check_slot_available(
        self,
        tenant_id: str,
        staff_ids: list[str],
        target_date: date,
        start_time: str,
        end_time: str,
        duration: int,
    ) -> bool:
        day_start = datetime.combine(target_date, time(0, 0))
        day_end = datetime.combine(target_date, time(23, 59, 59))

        result = await self.session.execute(
            select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.staff_id.in_(staff_ids),
                Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
                Appointment.start_time < day_end,
                Appointment.end_time > day_start,
            )
        )
        existing = result.scalars().all()

        new_start = time_to_minutes(start_time)
        new_end = time_to_minutes(end_time)

        for apt in existing:
            apt_start = apt.start_time.hour * 60 + apt.start_time.minute
            apt_end = apt.end_time.hour * 60 + apt.end_time.minute
            if new_start < apt_end and new_end > apt_start:
                return False

        return True
