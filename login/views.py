from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.views.decorators.cache import never_cache

# Create your views here.
def home (request):
    return render (request, 'login/vet_login.html')

@never_cache
def login_view (request):
    if request.method == "GET" and request.user.is_authenticated:
        return redirect('homeini')

    if request.method == "POST":

        username = request.POST.get('username')
        password = request.POST.get('password')

        # Verificar si el usuario existe
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)  # inicia sesión
            return redirect('homeini')  # cámbialo al nombre de tu página principal
        else:
            messages.error(request, "Usuario o contraseña incorrectos")

    return render(request, 'login/vet_login.html') 
