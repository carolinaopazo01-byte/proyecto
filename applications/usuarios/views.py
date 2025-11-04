# applications/usuarios/views.py
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
from django.template.loader import select_template, TemplateDoesNotExist
from django.contrib.auth import update_session_auth_hash

from applications.usuarios.utils import role_required
from applications.core.models import Comunicado
from .utils import normalizar_rut, formatear_rut
from .forms import UsuarioCreateForm, UsuarioUpdateForm, CambioPasswordForm

Usuario = get_user_model()


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
        rut_ingresado = (request.POST.get("rut") or "").strip()
        password = request.POST.get("password") or ""
        next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()

        # Variantes del rut para autenticación
        rut_norm = normalizar_rut(rut_ingresado)          # 12345678-9
        rut_fmt = formatear_rut(rut_norm)                 # 12.345.678-9
        rut_plain = rut_norm.replace("-", "")             # 123456789

        # authenticate usa el kw "username" incluso si USERNAME_FIELD es distinto
        user = (
            authenticate(request, username=rut_fmt,  password=password)
            or authenticate(request, username=rut_norm,  password=password)
            or authenticate(request, username=rut_plain, password=password)
        )

        if not user:
            return render(request, "usuarios/login.html", {"error": "RUT o contraseña incorrectos"})
        if not user.is_active:
            return render(request, "usuarios/login.html", {"error": "Usuario inactivo"})

        login(request, user)

        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return _redirigir_por_tipo(user)

    return render(request, "usuarios/login.html")


def logout_view(request):
    logout(request)
    return redirect("core:home")


# =================== Paneles ===================
@role_required(Usuario.Tipo.ADMIN)
def panel_admin(request):
    # Toma los últimos comunicados según el campo temporal disponible
    if hasattr(Comunicado, "creado"):
        comunicados = Comunicado.objects.order_by("-creado", "-id")[:8]
    elif hasattr(Comunicado, "fecha"):
        comunicados = Comunicado.objects.order_by("-fecha", "-id")[:8]
    elif hasattr(Comunicado, "created_at"):
        comunicados = Comunicado.objects.order_by("-created_at", "-id")[:8]
    else:
        comunicados = Comunicado.objects.order_by("-id")[:8]

    return render(request, "usuarios/panel_admin.html", {"comunicados": comunicados})


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
    return render(request, "pmul/panel.html")


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
            Q(rut__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(username__icontains=q)
            | Q(email__icontains=q)
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
        resp.write("\ufeff")  # BOM para Excel
        headers = ["RUT", "Nombre", "Usuario", "Rol", "Email", "Teléfono", "Estado"]
        resp.write(",".join(headers) + "\n")
        for u in qs:
            nombre = f"{u.first_name} {u.last_name}".strip()
            estado_txt = "Activo" if u.is_active else "Inactivo"
            fila = [
                u.rut or "",
                nombre,
                u.username or "",
                u.get_tipo_usuario_display() if hasattr(u, "get_tipo_usuario_display") else (u.tipo_usuario or ""),
                u.email or "",
                u.telefono or "",
                estado_txt,
            ]
            resp.write(",".join('"%s"' % (str(s).replace('"', '""')) for s in fila) + "\n")
        return resp

    ctx = {"items": qs, "q": q, "rol": rol, "estado": estado, "roles": Usuario.Tipo.choices}
    return render(request, "usuarios/usuarios_list.html", ctx)


# ====================== CRUD ======================
@role_required(Usuario.Tipo.ADMIN, Usuario.Tipo.COORD)
@require_http_methods(["GET", "POST"])
def usuario_create(request):
    if request.method == "POST":
        form = UsuarioCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado correctamente.")
            return redirect("usuarios:usuarios_list")
        messages.error(request, "Revisa los errores del formulario.")
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
            messages.success(request, "Usuario actualizado correctamente.")
            return redirect("usuarios:usuarios_list")
        messages.error(request, "Revisa los errores del formulario.")
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
        form = CambioPasswordForm(request.POST, user=request.user)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # mantener sesión tras cambio
            messages.success(request, "Contraseña actualizada correctamente.")

            # 1) Si viene ?next= volver ahí (si es seguro)
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)

            # 2) Si no, redirigir al panel según rol
            return _redirigir_por_tipo(request.user)
        else:
            messages.error(request, "Revisa los errores del formulario.")
    else:
        form = CambioPasswordForm(user=request.user)

    try:
        tpl = select_template([
            "atleta/cambiar_password.html",   # tu ruta actual
            "atletas/cambiar_password.html",  # tolerante por si lo mueves
            "usuarios/cambiar_password.html",
            "cambiar_password.html",
        ])
        return HttpResponse(tpl.render({"form": form}, request))
    except TemplateDoesNotExist:
        # Fallback mínimo (no te bloquea si aún no existe el template)
        html = """
        <h2>Cambiar contraseña</h2>
        <form method="post">
          {%% csrf_token %%}
          %s
          <p><button type="submit">Actualizar</button></p>
        </form>
        """ % (form.as_p(),)
        return HttpResponse(html)