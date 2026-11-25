from django.shortcuts import render
from django.views import View


class AnalysisPageView(View):
    def get(self, request):
        return render(request, "index.html")
