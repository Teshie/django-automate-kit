from django.db import models
from django.utils import timezone


class AutomateKitModel(models.Model):
    created_at = models.DateTimeField(default=timezone.localtime, editable=False)
    updated_at = models.DateTimeField(null=True, blank=True)
    exclude_model = False
    login_required = True
    exclude_fields = ("created_at", "updated_at")
    include_fields = ()

    model_permissions = ()
    import_id_fields = ()
    include_methods_fields = {}

    class Meta:
        abstract = True
