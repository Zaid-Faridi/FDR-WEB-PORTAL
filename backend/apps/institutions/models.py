from django.db import models

class InstitutionStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    PENDING = 'PENDING', 'Pending Approval'
    SUSPENDED = 'SUSPENDED', 'Suspended'


class Institution(models.Model):
    """
    AICTE-approved Technical Institution entity.
    """
    aicte_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="AICTE Permanent Institute ID")
    name = models.CharField(max_length=255, db_index=True)
    institution_type = models.CharField(max_length=100, default='Engineering & Technology')
    address = models.TextField(blank=True)
    state = models.CharField(max_length=100, db_index=True)
    district = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=20, choices=InstitutionStatus.choices, default=InstitutionStatus.ACTIVE)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Institution'
        verbose_name_plural = 'Institutions'

    def __str__(self):
        return f"{self.aicte_id} - {self.name}"
