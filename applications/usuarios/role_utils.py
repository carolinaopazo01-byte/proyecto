from django.urls import reverse

PMUL_ALIASES = {
    "PMUL", "EMUL", "MULTI", "PROF_MULTIDISCIPLINARIO",
    "PROFESIONAL_MULTIDISCIPLINARIO", "PROFESIONAL", "EQUIPO_MULTIDISCIPLINARIO",
}

def is_pmul(user):
    tipo = (getattr(user, "tipo_usuario", "") or "").upper()
    if tipo in PMUL_ALIASES:
        return True
    # si manejas roles por grupos:
    try:
        if user.groups.filter(name__iexact="Equipo Multidisciplinario").exists():
            return True
    except Exception:
        pass
    return False

def role_home_url(user):
    # Ajusta estas rutas a lo que tengas en tu proyecto
    if getattr(user, "is_superuser", False) or (getattr(user, "tipo_usuario", "").upper() == "ADMIN"):
        return reverse("usuarios:panel_admin")  # si lo tienes
    if (getattr(user, "tipo_usuario", "").upper() == "COORD"):
        return reverse("usuarios:panel_coordinador")  # si lo tienes
    if is_pmul(user):
        return reverse("pmul:panel")
    if (getattr(user, "tipo_usuario", "").upper() == "PROF"):
        return reverse("usuarios:panel_profesor")  # si lo tienes
    return reverse("usuarios:panel")  # tu panel genérico
