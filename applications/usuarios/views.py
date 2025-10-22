# applications/usuarios/views.py
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from .models import Usuario
from .utils import normalizar_rut
from .forms import UsuarioCreateForm, UsuarioUpdateForm
from applications.usuarios.utils import role_required

def normaliza_rut(r):
    if not r:
        return ""
    return r.replace(".", "").replace("-", "").strip().upper()

def _redirigir_por_tipo(user: Usuario):
    """Enruta al panel según el tipo de usuario."""
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

# Si tu modelo de usuario tiene el campo tipo_usuario, se usa para decidir el panel
@login_required
def panel_view(request):
    """
    Muestra el panel según el tipo de usuario:
    - ADMIN  → panel_admin.html
    - COORD  → panel_coordinador.html (sin gestión de usuarios)
    - Otros  → panel.html (panel genérico)
    """
    user = request.user
    rut = user.username
    tipo = getattr(user, "tipo_usuario", "").upper()

    context = {"rut": rut, "user": user}

    if tipo == "ADMIN":
        return render(request, "usuarios/panel_admin.html", context)

    elif tipo == "COORD":
        return render(request, "usuarios/panel_coordinador.html", context)

    else:
        return render(request, "usuarios/panel.html", context)

@csrf_protect
def login_rut(request):
    """
    Login por RUT + password.
    Requiere que el 'username' en la BD sea el RUT normalizado (sin puntos, con guion o sin él).
    """
    if request.method == "POST":
        rut = normaliza_rut(request.POST.get("rut", ""))
        password = request.POST.get("password", "")

        # Puedes mapear rut->username aquí si tu username guarda el RUT sin guión:
        username = rut  # ajusta si tu BD guarda otro formato

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            # redirige al panel unificado
            return redirect("usuarios:panel")
        else:
            return render(request, "usuarios/login.html", {"error": "RUT o contraseña inválidos."})

    # GET: mostrar el form (esto hace que Django setee la cookie CSRF)
    return render(request, "usuarios/login.html")

def logout_view(request):
    logout(request)
    return redirect("core:home")


# =================== Paneles ===================
@role_required(Usuario.Tipo.ADMIN)
def panel_admin(request):
    return render(request, "usuarios/panel_admin.html")


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


@role_required(Usuario.Tipo.ATLE)
def panel_atleta(request):
    return render(request, "usuarios/panel_atleta.html")


# ========== Listado + filtros + export ==========
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

    # Export CSV (Excel-friendly UTF-8 con BOM)
    if request.GET.get("export") == "1":
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="usuarios.csv"'
        resp.write("\ufeff")  # BOM
        headers = ["RUT", "Nombre", "Usuario", "Rol", "Email", "Teléfono", "Estado"]
        resp.write(",".join(headers) + "\n")
        for u in qs:
            nombre = f"{u.first_name} {u.last_name}".strip()
            estado_txt = "Activo" if u.is_active else "Inactivo"
            fila = [u.rut, nombre, u.username, u.get_tipo_usuario_display(), u.email or "", u.telefono or "", estado_txt]
            resp.write(",".join('"%s"' % (s.replace('"', '""')) for s in fila) + "\n")
        return resp

    ctx = {
        "items": qs,
        "q": q,
        "rol": rol,
        "estado": estado,
        "roles": Usuario.Tipo.choices,
    }
    return render(request, "usuarios/usuarios_list.html", ctx)


# ====================== CRUD ======================
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
