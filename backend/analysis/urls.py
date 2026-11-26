from django.urls import path

from .views import AnalysisPageView

urlpatterns = [
    path('', AnalysisPageView.as_view()),
]