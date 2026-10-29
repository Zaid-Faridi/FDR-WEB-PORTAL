import re
from django.core.exceptions import ValidationError


class ComplexityPasswordValidator:
    """
    Phase 7 Password Policy Validator:
    Enforces strong password complexity requirements for regulatory portal accounts:
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 numeric digit
    - At least 1 special character
    """
    def validate(self, password, user=None):
        if len(password) < 10:
            raise ValidationError(
                "Password must be at least 10 characters long.",
                code='password_too_short',
            )
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                "Password must contain at least one uppercase letter (A-Z).",
                code='password_no_upper',
            )
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                "Password must contain at least one lowercase letter (a-z).",
                code='password_no_lower',
            )
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                "Password must contain at least one numeric digit (0-9).",
                code='password_no_digit',
            )
        if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+;~`]', password):
            raise ValidationError(
                "Password must contain at least one special character (!@#$%^&*...).",
                code='password_no_special',
            )

    def get_help_text(self):
        return "Your password must contain at least one uppercase letter, one lowercase letter, one digit, and one special character."
