from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from .utils import role_required
from .models import Usuario
from .forms import UsuarioCreateForm, UsuarioEditForm

User = get_user_model()

@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET"])
def equipo_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = User.objects.all().order_by("last_name", "first_name")
    if q:
        qs = qs.filter(username__icontains=q) | qs.filter(first_name__icontains=q) | qs.filter(last_name__icontains=q) | qs.filter(rut__icontains=q)
    return render(request, "usuarios/equipo_list.html", {"items": qs, "q": q})

@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET","POST"])
def usuario_create(request):
    if request.method == "POST":
        form = UsuarioCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado.")
            return redirect("usuarios:equipo_list")
    else:
        form = UsuarioCreateForm()
    return render(request, "usuarios/usuario_form.html", {"form": form, "is_edit": False})

@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["GET","POST"])
def usuario_edit(request, user_id: int):
    obj = get_object_or_404(User, pk=user_id)
    if request.method == "POST":
        form = UsuarioEditForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Cambios guardados.")
            return redirect("usuarios:equipo_list")
    else:
        form = UsuarioEditForm(instance=obj)
    return render(request, "usuarios/usuario_form.html", {"form": form, "is_edit": True, "obj": obj})

@role_required(Usuario.Tipo.ADMIN)
@require_http_methods(["POST"])
def usuario_delete(request, user_id: int):
    obj = get_object_or_404(User, pk=user_id)
    obj.delete()
    messages.info(request, "Usuario eliminado.")
    return redirect("usuarios:equipo_list")
