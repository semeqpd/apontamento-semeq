from django.shortcuts import render
from django.views import View

# Create your views here.
def HomeView(request):
    return render(request, 'home/home.html')
