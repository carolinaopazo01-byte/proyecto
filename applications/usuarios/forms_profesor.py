# applications/usuarios/forms_profesor.py
from django import forms
from django.db.models import Q
from applications.core.models import Planificacion, Curso, Comunicado

class PlanificacionForm(forms.ModelForm):
    class Meta:
        model = Planificacion
        fields = ["curso", "semana", "archivo", "comentarios", "publica"]
        widgets = {
            "semana": forms.DateInput(attrs={"type": "date"}),
            "comentarios": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["curso"].queryset = Curso.objects.filter(profesor=user)


class ComunicadoForm(forms.Form):
    curso = forms.ModelChoiceField(
        queryset=Curso.objects.none(), required=False, label="Curso"
    )
    titulo = forms.CharField(max_length=200, label="Título")
    cuerpo = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), label="Cuerpo")
    publico = forms.BooleanField(required=False, initial=False, label="¿Pública?")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # limitar cursos a los que el profe imparte o apoya
        if user is not None:
            self.fields["curso"].queryset = (
                Curso.objects.filter(Q(profesor=user) | Q(profesores_apoyo=user)).distinct()
            )