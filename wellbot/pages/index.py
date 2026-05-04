"""채팅 메인 페이지.

2단 레이아웃(Sidebar + 메시지 영역 + 입력 바) 채택.
자동 스크롤 스크립트를 페이지 레벨에서 초기화.
메시지 네비게이션(이전/다음/최하단) 기능 포함.
"""

import reflex as rx

from wellbot.components.chat.gnb import chat_gnb
from wellbot.components.chat.input_bar import input_bar
from wellbot.components.chat.message_area import message_area, message_nav_panel
from wellbot.components.layout import chat_layout
from wellbot.constants import BTN_THRESHOLD, SCROLL_THRESHOLD


# 자동 스크롤 + 메시지 네비게이션 JavaScript
# - MutationObserver로 메시지 영역 내 DOM 변경 감지
# - 사용자가 하단 근처에 있을 때만 자동 스크롤
# - 사용자가 위로 스크롤하면 자동 스크롤 중단
# - 네비게이션 패널 표시/숨김 제어
# - 이전/다음 메시지 이동 + 최하단 이동
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
        // 현재 포커스된 메시지 인덱스 (-1 = 없음)
        var currentMsgIdx = -1;

        function distFromBottom() {
            return el.scrollHeight - el.scrollTop - el.clientHeight;
        }

        function scrollToBottom() {
            el.scrollTop = el.scrollHeight;
        }

        function getMessages() {
            return el.querySelectorAll('.chat-message');
        }

        function updateNavPanel() {
            var panel = document.getElementById('msg-nav-panel');
            if (!panel) return;
            var msgs = getMessages();
            var hasContent = msgs.length > 0;
            var isScrollable = el.scrollHeight > el.clientHeight;
            // 메시지가 있고 스크롤 가능할 때만 표시 (visibility로 제어)
            if (hasContent && isScrollable) {
                panel.style.visibility = 'visible';
                panel.style.opacity = '1';
            } else {
                panel.style.visibility = 'hidden';
                panel.style.opacity = '0';
            }

            // 버튼 disabled 상태 업데이트
            var prevBtn = document.getElementById('nav-prev-msg');
            var nextBtn = document.getElementById('nav-next-msg');
            var bottomBtn = document.getElementById('nav-scroll-bottom');

            if (prevBtn) {
                // 최상단이면 이전 버튼 비활성화
                prevBtn.disabled = (el.scrollTop <= 5);
                prevBtn.style.opacity = prevBtn.disabled ? '0.3' : '';
            }
            if (nextBtn) {
                // 최하단이면 다음 버튼 비활성화
                nextBtn.disabled = (distFromBottom() < BTN_THRESHOLD);
                nextBtn.style.opacity = nextBtn.disabled ? '0.3' : '';
            }
            if (bottomBtn) {
                bottomBtn.disabled = (distFromBottom() < BTN_THRESHOLD);
                bottomBtn.style.opacity = bottomBtn.disabled ? '0.3' : '';
            }
        }

        // 현재 뷰포트에서 가장 위에 보이는 메시지 인덱스 찾기
        function findVisibleMsgIndex() {
            var msgs = getMessages();
            var containerTop = el.getBoundingClientRect().top;
            for (var i = 0; i < msgs.length; i++) {
                var rect = msgs[i].getBoundingClientRect();
                // 메시지 상단이 컨테이너 상단 아래에 있으면 현재 보이는 메시지
                if (rect.top >= containerTop - 10) {
                    return i;
                }
            }
            // 모두 위에 있으면 마지막 메시지
            return msgs.length > 0 ? msgs.length - 1 : -1;
        }

        // 특정 인덱스의 메시지로 스크롤
        function scrollToMsg(idx) {
            var msgs = getMessages();
            if (idx < 0 || idx >= msgs.length) return;
            currentMsgIdx = idx;
            userScrolledUp = (idx < msgs.length - 1);
            msgs[idx].scrollIntoView({ behavior: 'smooth', block: 'start' });
            // 스크롤 완료 후 상태 업데이트
            setTimeout(updateNavPanel, 300);
        }

        // 이전 메시지로 이동
        function goToPrevMsg() {
            var msgs = getMessages();
            if (msgs.length === 0) return;
            var visIdx = findVisibleMsgIndex();
            // 현재 보이는 메시지의 이전으로
            var target = Math.max(0, visIdx - 1);
            scrollToMsg(target);
        }

        // 다음 메시지로 이동
        function goToNextMsg() {
            var msgs = getMessages();
            if (msgs.length === 0) return;
            var visIdx = findVisibleMsgIndex();
            var target = Math.min(msgs.length - 1, visIdx + 1);
            scrollToMsg(target);
        }

        // 최하단으로 이동
        function goToBottom() {
            userScrolledUp = false;
            currentMsgIdx = -1;
            scrollToBottom();
            setTimeout(updateNavPanel, 100);
        }

        el.addEventListener('scroll', function() {
            var dist = distFromBottom();
            if (dist >= SCROLL_THRESHOLD) {
                userScrolledUp = true;
            } else if (dist < BTN_THRESHOLD) {
                userScrolledUp = false;
                currentMsgIdx = -1;
            }
            updateNavPanel();
        });

        // 네비게이션 버튼 클릭 이벤트
        document.addEventListener('click', function(e) {
            var target = e.target.closest('button');
            if (!target) return;
            if (target.id === 'nav-prev-msg') {
                e.preventDefault();
                goToPrevMsg();
            } else if (target.id === 'nav-next-msg') {
                e.preventDefault();
                goToNextMsg();
            } else if (target.id === 'nav-scroll-bottom') {
                e.preventDefault();
                goToBottom();
            }
        });

        var observer = new MutationObserver(function() {
            if (!userScrolledUp) {
                scrollToBottom();
            }
            updateNavPanel();
        });

        observer.observe(el, {
            childList: true,
            subtree: true,
            characterData: true,
        });

        // 대화 전환 시 호출: 상태 리셋 + 스크롤
        window.__resetAutoScroll = function() {
            userScrolledUp = false;
            currentMsgIdx = -1;
            scrollToBottom();
            updateNavPanel();
        };

        scrollToBottom();
        updateNavPanel();
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
    """메인 대화 영역: GNB + 메시지 표시 + 입력 바(+ 네비게이션 패널)."""
    return rx.vstack(
        chat_gnb(),
        message_area(),
        # 입력 바 + 우측 네비게이션 패널을 hstack으로 배치
        rx.hstack(
            input_bar(),
            message_nav_panel(),
            width="100%",
            spacing="0",
            align="end",
            flex_shrink="0",
        ),
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
