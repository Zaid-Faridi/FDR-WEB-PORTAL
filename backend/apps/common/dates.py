import os
from datetime import datetime, date, time
from typing import Optional, Union, Dict, Any
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

SIMULATED_DATE_KEY = 'SIMULATED_SYSTEM_DATE'


def is_simulation_allowed() -> bool:
    """
    Guards simulated dates:
    NEVER allowed in production mode.
    Must have settings.ALLOW_SIMULATED_DATE = True.
    """
    env = getattr(settings, 'ENVIRONMENT', 'development').lower()
    allow_flag = getattr(settings, 'ALLOW_SIMULATED_DATE', True)
    if env == 'production' or not allow_flag:
        return False
    return True


def get_effective_date() -> date:
    """
    Returns the effective date for all FDR computations,
    maturity tracking, reminders, and escalation logic.
    In demo mode, uses the admin-configured simulated date if present.
    In production mode or if unset, always returns timezone.now().date().
    """
    if not is_simulation_allowed():
        return timezone.now().date()

    try:
        from apps.common.models import SystemSetting
        setting = SystemSetting.objects.filter(key=SIMULATED_DATE_KEY).first()
        if setting and setting.value:
            val = setting.value
            if isinstance(val, dict):
                date_str = val.get('date')
            elif isinstance(val, str):
                date_str = val
            else:
                date_str = None

            if date_str:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        # Fallback safely to real date if database or table is unavailable during initialization
        pass

    return timezone.now().date()


def get_effective_datetime() -> datetime:
    """
    Returns effective datetime corresponding to effective date at current time.
    """
    eff_date = get_effective_date()
    now_time = timezone.now().time()
    current_tz = timezone.get_current_timezone()
    dt = datetime.combine(eff_date, now_time)
    return timezone.make_aware(dt, current_tz) if timezone.is_naive(dt) else dt


def get_simulated_date_info() -> Dict[str, Any]:
    """
    Returns diagnostic status of date simulation.
    """
    allowed = is_simulation_allowed()
    sim_date_str = None
    is_active = False

    if allowed:
        try:
            from apps.common.models import SystemSetting
            setting = SystemSetting.objects.filter(key=SIMULATED_DATE_KEY).first()
            if setting and setting.value:
                val = setting.value
                date_str = val.get('date') if isinstance(val, dict) else (val if isinstance(val, str) else None)
                if date_str:
                    sim_date_str = date_str
                    is_active = True
        except Exception:
            pass

    eff_date = get_effective_date()
    real_today = timezone.now().date()

    return {
        'is_simulation_allowed': allowed,
        'is_active': is_active,
        'simulated_date': sim_date_str,
        'effective_date': eff_date.isoformat(),
        'real_today': real_today.isoformat(),
        'environment': getattr(settings, 'ENVIRONMENT', 'development'),
    }


def set_simulated_date(target_date: Optional[Union[str, date]], username: str = 'system') -> Dict[str, Any]:
    """
    Sets or resets the simulated date for demo and testing.
    Guarded strictly: blocked in production.
    """
    if not is_simulation_allowed():
        raise PermissionDenied("Simulated dates are strictly disabled in production mode.")

    from apps.common.models import SystemSetting
    from apps.common.audit import record_audit_event

    prev_info = get_simulated_date_info()

    if target_date is None or (isinstance(target_date, str) and not target_date.strip()):
        # Clear simulated date
        SystemSetting.objects.filter(key=SIMULATED_DATE_KEY).delete()
        record_audit_event(
            action='SIMULATED_DATE_CLEARED',
            entity_type='SystemSetting',
            entity_id=SIMULATED_DATE_KEY,
            actor_username=username,
            actor_role='ADMIN',
            previous_state={'simulated_date': prev_info['simulated_date']},
            new_state={'simulated_date': None, 'effective_date': timezone.now().date().isoformat()},
        )
        return get_simulated_date_info()

    if isinstance(target_date, date):
        date_str = target_date.isoformat()
    elif isinstance(target_date, str):
        try:
            parsed = datetime.strptime(target_date.strip(), '%Y-%m-%d').date()
            date_str = parsed.isoformat()
        except ValueError:
            raise ValidationError(f"Invalid date format '{target_date}'. Expected YYYY-MM-DD.")
    else:
        raise ValidationError("target_date must be a date object or 'YYYY-MM-DD' string.")

    setting, _ = SystemSetting.objects.get_or_create(
        key=SIMULATED_DATE_KEY,
        defaults={'description': 'Demo-only simulated system date'}
    )
    setting.value = {'date': date_str}
    setting.updated_by_username = username
    setting.save()

    record_audit_event(
        action='SIMULATED_DATE_SET',
        entity_type='SystemSetting',
        entity_id=SIMULATED_DATE_KEY,
        actor_username=username,
        actor_role='ADMIN',
        previous_state={'simulated_date': prev_info['simulated_date']},
        new_state={'simulated_date': date_str, 'effective_date': date_str},
    )

    return get_simulated_date_info()
