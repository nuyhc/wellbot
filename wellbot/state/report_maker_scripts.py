"""보고서 문구 작성 지원 — 브라우저 업로드 JS (페이지 레벨 window-global).

report_checker_scripts 와 동일한 backendBase 결정 규칙을 사용한다.
  - reportMakerPickAndUpload(template, kind): 단일 파일 선택 → 업로드
    → {key, filename, error} 반환(취소 시 {key:'', error:''}). (주제 첨부용)
  - reportMakerPickAndUploadMany(template, kind): 다중 파일 선택 → 순차 업로드
    → [{key, filename, error}, ...] 반환(취소 시 []). (참고 문서 학습용)
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

// 단일 파일 업로드(공유 헬퍼). 성공/실패 모두 {key, filename, error} 로 반환.
window._rmUploadOne = window._rmUploadOne || async function(file, template, kind) {
    var form = new FormData();
    form.append('file', file);
    form.append('template', template || '');
    form.append('kind', kind || 'style');
    try {
        var base = await window._rmBackendBase();
        var resp = await fetch(base + '/api/report_maker/upload', {
            method: 'POST', body: form, credentials: 'include'
        });
        var result = await resp.json().catch(function() { return {}; });
        if (!resp.ok) {
            return {key: '', filename: file.name,
                    error: (result && result.detail) ? result.detail : ('업로드 실패 (' + resp.status + ')')};
        }
        return result;
    } catch (e) {
        return {key: '', filename: file.name, error: (e && e.message) ? e.message : String(e)};
    }
};

// 파일 선택 input 을 만들어 클릭 → onPick(files[]) 콜백 실행. 취소 시 빈 배열.
window._rmPickFiles = window._rmPickFiles || function(accept, multiple, onPick) {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    if (multiple) input.multiple = true;
    input.style.display = 'none';
    input.onchange = function() {
        var files = input.files ? Array.prototype.slice.call(input.files) : [];
        try { document.body.removeChild(input); } catch (e) {}
        onPick(files);
    };
    input.addEventListener('cancel', function() {
        try { document.body.removeChild(input); } catch (e) {}
        onPick([]);
    });
    document.body.appendChild(input);
    input.click();
};

// 단일 파일(주제 첨부). {key, filename, error} 반환(취소 시 {key:'', error:''}).
window.reportMakerPickAndUpload = function(template, kind) {
    var accept = (kind === 'topic')
        ? '.pdf,.pptx,.png,.jpg,.jpeg,.webp,.gif'
        : '.pdf,.pptx';
    return new Promise(function(resolve) {
        window._rmPickFiles(accept, false, async function(files) {
            if (!files.length) { resolve({key: '', filename: '', error: ''}); return; }
            resolve(await window._rmUploadOne(files[0], template, kind));
        });
    });
};

// 다중 파일(참고 문서 학습). 순차 업로드 → [{key, filename, error}, ...] 반환(취소 시 []).
window.reportMakerPickAndUploadMany = function(template, kind) {
    var accept = (kind === 'topic')
        ? '.pdf,.pptx,.png,.jpg,.jpeg,.webp,.gif'
        : '.pdf,.pptx';
    return new Promise(function(resolve) {
        window._rmPickFiles(accept, true, async function(files) {
            var results = [];
            for (var i = 0; i < files.length; i++) {
                results.push(await window._rmUploadOne(files[i], template, kind));
            }
            resolve(results);
        });
    });
};
"""
