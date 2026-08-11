
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect

# Create your views here.
def HomeView(request):
    return render(request, 'home/home.html')


def create_user(request):
    if request.method == "POST":
        pass
        # user.set_password("NovaSenha456!")
        # user.save()

def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect("home")

    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return redirect("login")  