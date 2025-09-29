from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='usuarios/login.html'), name='core_login'),
    path('sedes/', views.sede_list, name='sede_list'),
    path('deportes/', views.deporte_list, name='deporte_list'),
]
