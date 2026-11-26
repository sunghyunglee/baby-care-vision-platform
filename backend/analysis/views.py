import requests
from django.conf import settings
from django.shortcuts import render
from django.views import View
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AnalysisSerializer

AI_TIMEOUT_SECONDS = 60


class AnalysisPageView(View):
    def get(self, request):
        return render(request, "index.html")


class AnalysisAPIView(APIView):
    def post(self, request):
        serializer = AnalysisSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        analysis = serializer.save()

        with analysis.video.open("rb") as video_file:
            ai_response = requests.post(
                f"{settings.AI_SERVICE_URL}/predict",
                files={"file": video_file},
                timeout=AI_TIMEOUT_SECONDS,
            )
        ai_response.raise_for_status()

        analysis.result = ai_response.json()["result"]
        analysis.save(update_fields=["result"])
        return Response(AnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
