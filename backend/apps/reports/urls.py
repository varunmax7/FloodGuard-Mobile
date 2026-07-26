"""reports/urls.py"""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.submit_report, name="report-submit"),
    path("nearby/", views.nearby_reports, name="reports-nearby"),
    path("heatmap/", views.reports_heatmap, name="reports-heatmap"),
]
