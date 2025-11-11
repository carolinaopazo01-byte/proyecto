# applications/usuarios/views.py
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.contrib import messages  # opcional
from django.contrib.auth.decorators import login_required
from django.template import TemplateDoesNotExist

from .models import Usuario
from .utils import normalizar_rut
from .forms import UsuarioCreateForm, UsuarioUpdateForm
from applications.usuarios.utils import role_required


from applications.core.models import Comunicado


def _redirigir_por_tipo(user: Usuario):
    t = user.tipo_usuario
    if t == Usuario.Tipo.ADMIN:
        return redirect("usuarios:panel_admin")
    if t == Usuario.Tipo.COORD:
        return redirect("usuarios:panel_coordinador")
    if t == Usuario.Tipo.PROF:
        return redirect("usuarios:panel_profesor")
    if t == Usuario.Tipo.APOD:
        return redirect("usuarios:panel_apoderado")
    if t == Usuario.Tipo.PMUL:
        return redirect("usuarios:panel_prof_multidisciplinario")
    return redirect("usuarios:panel_atleta")


@require_http_methods(["GET", "POST"])
def login_rut(request):
    if request.method == "POST":
        rut_ingresado = request.POST.get("rut") or ""
        password = request.POST.get("password") or ""
        next_url = request.POST.get("next") or request.GET.get("next") or ""

        # Normaliza el formato del RUT (por si viene con puntos o guión)
        rut_norm = normalizar_rut(rut_ingresado)  # Ej: 12345678-9
        rut_sin_guion = rut_norm.replace(".", "").replace("-", "")  # Ej: 123456789


        user = authenticate(request, username=rut_norm, password=password)
        if not user:
            user = authenticate(request, username=rut_sin_guion, password=password)

        if not user:
            return render(request, "usuarios/login.html", {"error": "RUT o contraseña incorrectos"})
        if not user.is_active:
            return render(request, "usuarios/login.html", {"error": "Usuario inactivo"})

        login(request, user)
        if next_url:
            return redirect(next_url)
        return _redirigir_por_tipo(user)

    return render(request, "usuarios/login.html")



def logout_view(request):
    logout(request)
    return redirect("core:home")


# =================== Paneles ===================
@role_required(Usuario.Tipo.ADMIN)
def panel_admin(request):


    if hasattr(Comunicado, "creado"):
        comunicados = Comunicado.objects.order_by("-creado", "-id")[:8]
    elif hasattr(Comunicado, "fecha"):
        comunicados = Comunicado.objects.order_by("-fecha", "-id")[:8]
    elif hasattr(Comunicado, "created_at"):
        comunicados = Comunicado.objects.order_by("-created_at", "-id")[:8]
    else:
        comunicados = Comunicado.objects.order_by("-id")[:8]

    return render(request, "usuarios/panel_admin.html", {
        "comunicados": comunicados,
    })


@role_required(Usuario.Tipo.COORD)
def panel_coordinador(request):
    return render(request, "usuarios/panel_coordinador.html")


@role_required(Usuario.Tipo.PROF)
def panel_profesor(request):
    return render(request, "usuarios/panel_profesor.html")


@role_required(Usuario.Tipo.APOD)
def panel_apoderado(request):
    return render(request, "usuarios/panel_apoderado.html")


@role_required(Usuario.Tipo.PMUL)
def panel_prof_multidisciplinario(request):
    return render(request, "usuarios/panel_prof_multidisciplinario.html")

@login_required
def panel_atleta(request):
    try:
        return render(request, "usuarios/panel_atleta.html")
    except TemplateDoesNotExist as e:
        return HttpResponse(f"❌ Template no encontrado: {e}", status=500)


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def usuarios_list(request):
    q = (request.GET.get("q") or "").strip()
    rol = (request.GET.get("rol") or "").strip()
    estado = (request.GET.get("estado") or "").strip()  # "act" | "inact" | ""

    qs = Usuario.objects.all().order_by("last_name", "first_name")

    if q:
        qs = qs.filter(
            Q(rut__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q)
        )
    if rol:
        qs = qs.filter(tipo_usuario=rol)
    if estado == "act":
        qs = qs.filter(is_active=True)
    elif estado == "inact":
        qs = qs.filter(is_active=False)

    if request.GET.get("export") == "1":
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="usuarios.csv"'
        resp.write("\ufeff")
        headers = ["RUT", "Nombre", "Usuario", "Rol", "Email", "Teléfono", "Estado"]
        resp.write(",".join(headers) + "\n")
        for u in qs:
            nombre = f"{u.first_name} {u.last_name}".strip()
            estado_txt = "Activo" if u.is_active else "Inactivo"
            fila = [
                u.rut,
                nombre,
                u.username,
                u.get_tipo_usuario_display(),
                u.email or "",
                u.telefono or "",
                estado_txt,
            ]
            resp.write(",".join('"%s"' % (s.replace('"', '""')) for s in fila) + "\n")
        return resp

    ctx = {"items": qs, "q": q, "rol": rol, "estado": estado, "roles": Usuario.Tipo.choices}
    return render(request, "usuarios/usuarios_list.html", ctx)



@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def usuario_create(request):
    if request.method == "POST":
        form = UsuarioCreateForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("usuarios:usuarios_list")
    else:
        form = UsuarioCreateForm()
    return render(request, "usuarios/usuario_form.html", {"form": form, "is_edit": False})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET"])
def usuario_detail(request, usuario_id: int):
    u = get_object_or_404(Usuario, pk=usuario_id)
    return render(request, "usuarios/usuario_detail.html", {"u": u})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def usuario_edit(request, usuario_id: int):
    u = get_object_or_404(Usuario, pk=usuario_id)
    if request.method == "POST":
        form = UsuarioUpdateForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            return redirect("usuarios:usuarios_list")
    else:
        form = UsuarioUpdateForm(instance=u)
    return render(request, "usuarios/usuario_form.html", {"form": form, "is_edit": True, "u": u})


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def usuario_toggle_active(request, usuario_id: int):
    u = get_object_or_404(Usuario, pk=usuario_id)
    u.is_active = not u.is_active
    u.save(update_fields=["is_active"])
    return redirect("usuarios:usuarios_list")


@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["POST"])
def usuario_delete(request, usuario_id: int):
    get_object_or_404(Usuario, pk=usuario_id).delete()
    return redirect("usuarios:usuarios_list")

@login_required
def cambiar_password(request):
    if request.method == "POST":
        pwd_old = request.POST.get("pwd_old")
        pwd1 = request.POST.get("pwd1")
        pwd2 = request.POST.get("pwd2")

        if not request.user.check_password(pwd_old):
            messages.error(request, "La contraseña actual no es correcta.")
        elif pwd1 != pwd2:
            messages.error(request, "Las contraseñas nuevas no coinciden.")
        elif len(pwd1) < 6:
            messages.error(request, "La nueva contraseña debe tener al menos 6 caracteres.")
        else:
            request.user.set_password(pwd1)
            request.user.save()
            messages.success(request, "Contraseña actualizada correctamente. Vuelve a iniciar sesión.")
            return redirect("usuarios:login_rut")

    return render(request, "usuarios/cambiar_password.html")