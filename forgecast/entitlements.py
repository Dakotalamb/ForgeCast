"""Runtime-only feature access verified by the authenticated Hub response."""
import time
from urllib.parse import urlparse

def accept_entitlements(s,response):
    flags=response.get('entitlements',{})
    source=urlparse(s.config.get('hub_url',''))
    trusted=(source.scheme=='https' and source.hostname=='hub.forgeddestinygaming.com' and source.port in (None,443) and not source.username and not source.password and source.path in ('','/') and not source.query and not source.fragment)
    granted=trusted and isinstance(flags,dict) and flags.get('fdgcast_overlays') is True
    s.overlay_access_granted=granted
    s.overlay_access_until=time.monotonic()+900 if granted else 0

def overlay_access(s):return bool(getattr(s,'overlay_access_granted',False) and time.monotonic()<getattr(s,'overlay_access_until',0))

def require_overlays(s):
    if not overlay_access(s):raise ValueError('Live overlays require paid or complimentary access verified by your paired Hub. Sync linked accounts to check access.')
