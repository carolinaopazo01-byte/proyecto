from django.contrib import admin
from .models import Sede, Deporte, SedeDeporte, Evento, Comunicado

admin.site.register(Sede)
admin.site.register(Deporte)
admin.site.register(SedeDeporte)
admin.site.register(Evento)
admin.site.register(Comunicado)
