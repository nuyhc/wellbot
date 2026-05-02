"""채팅 메인 페이지.

2단 레이아웃(Sidebar + 메시지 영역 + 입력 바) 채택.
자동 스크롤 스크립트를 페이지 레벨에서 초기화.
"""

import reflex as rx

from wellbot.components.chat.gnb import chat_gnb
from wellbot.components.chat.input_bar import input_bar
from wellbot.components.chat.message_area import message_area
from wellbot.components.layout import chat_layout
from wellbot.constants import BTN_THRESHOLD, SCROLL_THRESHOLD


# 자동 스크롤 JavaScript
# - MutationObserver로 메시지 영역 내 DOM 변경 감지
# - 사용자가 하단 근처에 있을 때만 자동 스크롤
# - 사용자가 위로 스크롤하면 자동 스크롤 중단
# - "맨 아래로" 버튼 표시/숨김 제어
# - setInterval로 DOM 준비될 때까지 폴링
AUTO_SCROLL_SCRIPT = """
(function initAutoScroll() {
    var SCROLL_THRESHOLD = __SCROLL_THRESHOLD__;
    var BTN_THRESHOLD = __BTN_THRESHOLD__;

    function setup() {
        var el = document.getElementById('message-area');
        if (!el) return false;

        // 이미 설정된 경우 스킵
        if (el._asReady) return true;
        el._asReady = true;

        var userScrolledUp = false;

        function distFromBottom() {
            return el.scrollHeight - el.scrollTop - el.clientHeight;
        }

        function scrollToBottom() {
            el.scrollTop = el.scrollHeight;
        }

        function updateBtn() {
            var btn = document.getElementById('scroll-to-bottom-btn');
            if (!btn) return;
            btn.style.display = (userScrolledUp && el.scrollHeight > el.clientHeight) ? 'flex' : 'none';
        }

        el.addEventListener('scroll', function() {
            var dist = distFromBottom();
            if (dist >= SCROLL_THRESHOLD) {
                userScrolledUp = true;
            } else if (dist < BTN_THRESHOLD) {
                userScrolledUp = false;
            }
            updateBtn();
        });

        el.addEventListener('click', function(e) {
            if (e.target.closest('#scroll-to-bottom-btn')) {
                userScrolledUp = false;
                scrollToBottom();
                updateBtn();
            }
        });

        var observer = new MutationObserver(function() {
            if (!userScrolledUp) {
                scrollToBottom();
            }
            updateBtn();
        });

        observer.observe(el, {
            childList: true,
            subtree: true,
            characterData: true,
        });

        // 대화 전환 시 호출: userScrolledUp 리셋 + 스크롤
        window.__resetAutoScroll = function() {
            userScrolledUp = false;
            scrollToBottom();
            updateBtn();
        };

        scrollToBottom();
        return true;
    }

    // DOM이 준비될 때까지 폴링
    if (!setup()) {
        var attempts = 0;
        var timer = setInterval(function() {
            attempts++;
            if (setup() || attempts > 50) {
                clearInterval(timer);
            }
        }, 100);
    }
})();
""".replace("__SCROLL_THRESHOLD__", str(SCROLL_THRESHOLD)).replace("__BTN_THRESHOLD__", str(BTN_THRESHOLD))


def chat_main() -> rx.Component:
    """메인 대화 영역: GNB + 메시지 표시 + 입력 바."""
    return rx.vstack(
        chat_gnb(),
        message_area(),
        input_bar(),
        height="100%",
        width="100%",
        spacing="0",
        position="relative",
    )


def index() -> rx.Component:
    """채팅 메인 페이지."""
    return rx.fragment(
        rx.script(AUTO_SCROLL_SCRIPT),
        chat_layout(chat_main()),
    )
