# applications/core/context_processors.py
from django.utils import timezone
from .models import PortalConfig

def portal_config(request):

    cfg = None
    try:
        cfg = PortalConfig.get_solo()
    except Exception:
        # Si aún no hay tabla/migración, evita romper el render
        cfg = None

    hoy = timezone.localdate()
    visible = False
    if cfg and cfg.registro_habilitado:
        dentro_inicio = (cfg.registro_inicio is None) or (cfg.registro_inicio <= hoy)
        dentro_fin    = (cfg.registro_fin    is None) or (hoy <= cfg.registro_fin)
        visible = dentro_inicio and dentro_fin

    return {
        "PORTAL_CFG": cfg,
        "REGISTRO_VISIBLE": visible,
    }
