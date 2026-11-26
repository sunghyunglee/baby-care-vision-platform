from django.db import models


class Analysis(models.Model):
    video = models.FileField(upload_to='videos/')
    result = models.CharField(max_length=10, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)