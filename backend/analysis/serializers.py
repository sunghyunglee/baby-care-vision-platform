from rest_framework import serializers

from .models import Analysis


class AnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analysis
        fields = ["video", "result"]
        extra_kwargs = {
            "video": {"write_only": True},
            "result": {"read_only": True},
        }
        