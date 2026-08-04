from django.urls import path
from . import views

app_name = 'semeq'

urlpatterns = [
  path('', views.HomeView, name='home'),
]