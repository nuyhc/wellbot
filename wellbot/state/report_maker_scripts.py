"""보고서 문구 작성 지원 — 브라우저 업로드 JS (페이지 레벨 window-global).

report_checker_scripts 와 동일한 backendBase 결정 규칙을 사용한다.
  - reportMakerPickAndUpload(template, kind): 파일 선택 → /api/report_maker/upload 전송
    → {key, filename, error} 반환(취소 시 {key:'', error:''}).
정적 스크립트로, 페이지에서 rx.script 로 1회 등록한다.
"""

from __future__ import annotations

REPORT_MAKER_SCRIPT = """
window._rmBackendBase = window._rmBackendBase || async function() {
    try {
        var envResp = await fetch('/env.json');
        var env = await envResp.json();
        var pingUrl = env.PING || '';
        if (pingUrl) {
            var u = new URL(pingUrl);
            var loc = window.location;
            var isLocalDev = (
                (loc.hostname === 'localhost' || loc.hostname === '127.0.0.1') &&
                (u.hostname === 'localhost' || u.hostname === '127.0.0.1') &&
                u.port !== loc.port
            );
            if (isLocalDev) return loc.protocol + '//' + loc.hostname + ':' + u.port;
        }
    } catch (e) {}
    return '';
};

window.reportMakerPickAndUpload = function(template, kind) {
    return new Promise(function(resolve) {
        var accept = (kind === 'topic')
            ? '.pdf,.pptx,.png,.jpg,.jpeg,.webp,.gif'
            : '.pdf,.pptx';
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = accept;
        input.style.display = 'none';
        input.onchange = async function() {
            var f = (input.files && input.files[0]) || null;
            try { document.body.removeChild(input); } catch (e) {}
            if (!f) { resolve({key: '', filename: '', error: ''}); return; }
            var form = new FormData();
            form.append('file', f);
            form.append('template', template || '');
            form.append('kind', kind || 'style');
            try {
                var base = await window._rmBackendBase();
                var resp = await fetch(base + '/api/report_maker/upload', {
                    method: 'POST', body: form, credentials: 'include'
                });
                var result = await resp.json().catch(function() { return {}; });
                if (!resp.ok) {
                    resolve({key: '', filename: f.name,
                             error: (result && result.detail) ? result.detail : ('업로드 실패 (' + resp.status + ')')});
                    return;
                }
                resolve(result);
            } catch (e) {
                resolve({key: '', filename: f.name, error: (e && e.message) ? e.message : String(e)});
            }
        };
        input.addEventListener('cancel', function() {
            try { document.body.removeChild(input); } catch (e) {}
            resolve({key: '', filename: '', error: ''});
        });
        document.body.appendChild(input);
        input.click();
    });
};
"""
