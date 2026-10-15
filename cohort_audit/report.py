"""Self-contained report; imported text never becomes markup or executable code."""
import base64
import hashlib
from importlib.resources import files
from .core import AuditError, LIMITS, dumps


def render(result):
    serialized = dumps(result)
    raw = serialized.encode('utf-8')
    if len(raw) > LIMITS['json_bytes']:
        raise AuditError('JSON report byte limit exceeded')
    # Escape HTML raw-text termination, including hostile </script> labels.
    embedded = serialized.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    script = files('cohort_audit').joinpath('report.js').read_text('utf-8')
    style = files('cohort_audit').joinpath('report.css').read_text('utf-8')
    sha = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    style_sha = base64.b64encode(hashlib.sha256(style.encode()).digest()).decode()
    template = files('cohort_audit').joinpath('template.html').read_text('utf-8')
    html = template.replace('%%CSP_SCRIPT%%', sha).replace('%%CSP_STYLE%%', style_sha).replace('%%STYLE%%', style).replace('%%SCRIPT%%', script).replace('%%DATA%%', embedded).encode('utf-8')
    if len(html) > LIMITS['html_bytes']:
        raise AuditError('HTML report byte limit exceeded')
    return raw, html
