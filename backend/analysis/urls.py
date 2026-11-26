from django.urls import path

from .views import AnalysisAPIView, AnalysisPageView

urlpatterns = [
    path('', AnalysisPageView.as_view()),
    path('api/v1/analyses/', AnalysisAPIView.as_view()),
]