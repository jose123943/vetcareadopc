from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path ('', views.login_view , name = 'home-login'),
    path('logout/', LogoutView.as_view(next_page='home-login'), name='logout'),
]
