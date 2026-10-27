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

    def __str__(self):
        role_label = self.get_role_display()
        if self.institution:
            return f"{self.username} ({role_label} - {self.institution.aicte_id})"
        return f"{self.username} ({role_label})"
