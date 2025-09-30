from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # 👈 nuestra vista salir

urlpatterns = [
    path('login/',  auth_views.LoginView.as_view(template_name='usuarios/login.html'), name='login'),
    path('salir/',  views.salir, name='logout'),  # 👈 nuestra ruta
]
