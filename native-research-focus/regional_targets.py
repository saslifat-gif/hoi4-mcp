"""Select only an observed active, typed regional notification; never invoke native code.

The returned widget ID must be re-resolved against the live GUI registry and all
expected owner/provider/context fields immediately before a query. Source/name
alone is not a unique selector: ordinary entry constructors reuse a template.
"""

def select_regional_target(windows, *, scope, alert_kind, context_id):
    if scope not in ('region','theater') or type(alert_kind) is not int or not 0<=alert_kind<=81:
        raise ValueError('Invalid regional alert selector')
    if not isinstance(context_id,str) or not context_id.startswith('0x') or int(context_id,16)<=0:
        raise ValueError('Context must come from a current native notification observation')
    matches={}
    for window in windows:
        native=window.get('native_popup',{})
        if (native.get('alert_scope'),native.get('native_alert_kind'),native.get('native_context_id'))!=(scope,alert_kind,context_id):
            continue
        if native.get('status')=='cache_ambiguous':
            raise RuntimeError('Native alert context cache is ambiguous')
        if native.get('status')!='native_cached_text' or not native.get('runtime_binding_verified') or native.get('native_cache_record_active') is not True:
            continue
        if window.get('engine_local_shown') is not True or window.get('source')!='interface/theatreselector.gui':
            continue
        widget=window.get('widget_id')
        if not widget or not window.get('name') or not native.get('native_provider_id') or not native.get('native_owner_id'):
            raise RuntimeError('Regional notification identity incomplete')
        result={k:window[k] for k in ('widget_id','source','name')}
        result.update({k:native[k] for k in ('alert_scope','native_alert_kind','native_context_id','native_owner_id','native_provider_id')})
        if scope=='theater':
            handle=native.get('native_context_handle')
            if not isinstance(handle,list) or len(handle)!=2 or any(type(x) is not int or not 0<=x<2**32 for x in handle) or not any(handle):
                raise RuntimeError('Native theater context handle missing')
            result['native_context_handle']=handle
        if widget in matches and matches[widget]!=result:
            raise RuntimeError('Regional notification changed within observation')
        matches[widget]=result
    if not matches:
        raise RuntimeError('No observed active native regional notification for this context')
    if len(matches)!=1:
        raise RuntimeError('Regional notification selector is ambiguous; do not guess a widget')
    return next(iter(matches.values()))
