from django.contrib.auth.models import AbstractUser
from django.db import models

class UserRole(models.TextChoices):
    INSTITUTION = 'INSTITUTION', 'Institution'
    SCRUTINY_OFFICER = 'SCRUTINY_OFFICER', 'Scrutiny Officer'
    APPROVING_AUTHORITY = 'APPROVING_AUTHORITY', 'Approving Authority'
    ADMIN = 'ADMIN', 'Admin'


class User(AbstractUser):
    """
    Custom User model strictly linked to a system role and,
    for Institution users, an AICTE-approved institution.
    """
    role = models.CharField(
        max_length=30,
        choices=UserRole.choices,
        default=UserRole.INSTITUTION,
        db_index=True,
    )
    institution = models.ForeignKey(
        'institutions.Institution',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users',
        help_text="Associated technical institution (mandatory for Institution role).",
    )
    phone = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=100, blank=True)

    # Phase 7: Account Security & Lockout
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    # Phase 7: Optional TOTP 2FA for Officers and Approvers
    totp_secret = models.CharField(max_length=64, blank=True, default='')
    totp_enabled = models.BooleanField(default=False)

    @property
    def is_institution_user(self) -> bool:
        return self.role == UserRole.INSTITUTION

    @property
    def is_scrutiny_officer(self) -> bool:
        return self.role == UserRole.SCRUTINY_OFFICER or self.is_superuser

    @property
    def is_approving_authority(self) -> bool:
        return self.role == UserRole.APPROVING_AUTHORITY or self.is_superuser

    @property
    def is_admin_user(self) -> bool:
        return self.role == UserRole.ADMIN or self.is_superuser

    def is_locked_out(self, now=None) -> bool:
        """Returns True if the user account is currently locked due to failed logins."""
        from django.utils import timezone
        current = now or timezone.now()
        if self.locked_until and current < self.locked_until:
            return True
        return False

    def record_failed_login(self, ip_address=None) -> bool:
        """
        Increments failed login counter. If threshold (5) is reached,
        locks account for 15 minutes and returns True.
        """
        from datetime import timedelta
        from django.utils import timezone
        self.failed_login_attempts += 1
        is_now_locked = False
        if self.failed_login_attempts >= 5:
            self.locked_until = timezone.now() + timedelta(minutes=15)
            is_now_locked = True
        self.save(update_fields=['failed_login_attempts', 'locked_until'])
        return is_now_locked

    def reset_failed_logins(self):
        """Resets failed login counter and lockout on successful authentication."""
        if self.failed_login_attempts > 0 or self.locked_until is not None:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update_fields=['failed_login_attempts', 'locked_until'])

    def generate_totp_secret(self) -> str:
        """Generates a base32 TOTP secret if not present."""
        import pyotp
        if not self.totp_secret:
            self.totp_secret = pyotp.random_base32()
            self.save(update_fields=['totp_secret'])
        return self.totp_secret

    def get_totp_uri(self) -> str:
        """Generates the otpauth:// URI for authenticator app enrollment."""
        import pyotp
        secret = self.generate_totp_secret()
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=self.email or self.username,
            issuer_name='AICTE Security Deposit Portal'
        )

    def verify_totp(self, code: str) -> bool:
        """Verifies a 6-digit TOTP code against the user's secret."""
        import pyotp
        if not self.totp_secret or not code:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return bool(totp.verify(str(code).strip(), valid_window=1))

    def __str__(self):
        role_label = self.get_role_display()
        if self.institution:
            return f"{self.username} ({role_label} - {self.institution.aicte_id})"
        return f"{self.username} ({role_label})"
