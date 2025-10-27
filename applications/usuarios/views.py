# applications/usuarios/views.py
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse  # 👈 cambio

from .models import Usuario
from .utils import normalizar_rut
from .forms import UsuarioCreateForm, UsuarioUpdateForm

from applications.usuarios.utils import role_required, rut_equivalente

from datetime import date

User = get_user_model()

def normaliza_rut(r):
    if not r:
        return ""
    return r.replace(".", "").replace("-", "").strip().upper()

# ========= Helpers de rol (redirigir al home correcto) =========
PMUL_ALIASES = {
    "PMUL", "EMUL", "MULTI", "PROF_MULTIDISCIPLINARIO",
    "PROFESIONAL_MULTIDISCIPLINARIO", "PROFESIONAL", "EQUIPO_MULTIDISCIPLINARIO",
}

def is_pmul(user):
    tipo = (getattr(user, "tipo_usuario", "") or "").upper()
    return tipo in PMUL_ALIASES

def role_home_url(user):
    t = (getattr(user, "tipo_usuario", "") or "").upper()
    if getattr(user, "is_superuser", False) or t == "ADMIN":
        return reverse("usuarios:panel_admin")
    if t == "COORD":
        return reverse("usuarios:panel_coordinador")
    if t == "PROF":
        return reverse("usuarios:panel_profesor")
    if t == "APOD":
        return reverse("apoderado:dashboard")   # 👈 ESTA ES LA LÍNEA NUEVA
    if is_pmul(user):
        return reverse("pmul:panel")
    if t == "ATLE":
        return reverse("usuarios:panel_atleta")
    return reverse("usuarios:panel")

# ====== “Inicio” unificado (redirige por rol) ======
@login_required
def panel_view(request):
    rol = (getattr(request.user, "tipo_usuario", "") or "").upper()

    if rol == "PROF":
        return redirect("usuarios:panel_profesor")
    if rol == "ATLE":
        return redirect("usuarios:panel_atleta")
    if rol == "ADMIN":
        return redirect("usuarios:panel_admin")
    if rol == "COORD":
        return redirect("usuarios:panel_coordinador")
    if rol in {"PMUL","EMUL","MULTI","PROF_MULTIDISCIPLINARIO",
               "PROFESIONAL_MULTIDISCIPLINARIO","PROFESIONAL","EQUIPO_MULTIDISCIPLINARIO"}:
        return redirect("pmul:panel")  # o la ruta de tu panel PMUL

    # Fallback genérico si no hay rol reconocido
    return render(request, "usuarios/panel_generico.html")

@csrf_protect
def login_rut(request):
    if request.method == "POST":
        rut_in = (request.POST.get("rut") or "").strip()
        pwd    = (request.POST.get("password") or "")

        U = get_user_model()
        user_match = None

        try:
            user_match = U.objects.get(rut=rut_in, is_active=True)
        except U.DoesNotExist:
            eq = rut_equivalente(rut_in)
            for u in U.objects.filter(is_active=True).only("id", "rut", "tipo_usuario"):
                if rut_equivalente(u.rut) == eq:
                    user_match = u
                    break

        if user_match:
            # ⚠️ Nueva parte: bloqueo por edad
            if user_match.tipo_usuario == "ATLE" and user_match.fecha_nacimiento:
                edad = (date.today() - user_match.fecha_nacimiento).days // 365
                if edad < 18:
                    messages.error(request, "Solo los atletas mayores de edad pueden acceder al sistema.")
                    return render(request, "usuarios/login.html")

            user = authenticate(request, username=user_match.rut, password=pwd)
            if user is not None:
                login(request, user)
                return redirect("usuarios:panel")

        messages.error(request, "RUT o clave incorrectos.")
    return render(request, "usuarios/login.html")

def logout_view(request):
    logout(request)
    return redirect("core:home")


# =================== Paneles específicos (siguen disponibles) ===================
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
    # Puedes mantener esta vista antigua si alguna ruta la usa,
    # pero el home PMUL ahora es pmul:panel.
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

    if request.GET.get("export") == "1":
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="usuarios.csv"'
        resp.write("\ufeff")
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
