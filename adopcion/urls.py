from django.urls import path

from . import views

app_name = "adopcion"
urlpatterns = [
    path("api/", views.listar, name="listar"),
    path("api/datos/", views.datos, name="datos"),
    path("api/registrar/", views.registrar, name="registrar"),
    path("api/<int:adopcion_id>/adoptar/", views.adoptar, name="adoptar"),
    path("api/<int:adopcion_id>/cancelar/", views.cancelar, name="cancelar"),
    path("api/<int:adopcion_id>/evaluar/", views.evaluar, name="evaluar"),
    path("api/<int:adopcion_id>/evaluaciones/", views.evaluaciones, name="evaluaciones"),
]
