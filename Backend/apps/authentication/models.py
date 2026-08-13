from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Platform user scoped to a customer company.

    ``visibility`` acts as the user's role for authorization (commercial,
    technician, full) and drives future feature access.
    """

    class Visibility(models.TextChoices):
        COMMERCIAL = 'commercial', 'Commercial'
        TECHNICIAN = 'technician', 'Technician'
        FULL = 'full', 'Full'

    user_id = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        default='',
        help_text='Business identifier from CRM (e.g. USR-001).',
    )
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
    )
    job_title = models.CharField(max_length=128, blank=True, default='')
    visibility = models.CharField(
        max_length=32,
        choices=Visibility.choices,
        default=Visibility.FULL,
        help_text='Role controlling data visibility and agent permissions.',
    )

    class Meta:
        ordering = ['last_name', 'first_name']

    def save(self, *args, **kwargs) -> None:
        if not self.user_id:
            self.user_id = self.username
        super().save(*args, **kwargs)
