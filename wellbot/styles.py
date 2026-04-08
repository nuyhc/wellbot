"""디자인 토큰 및 테마 설정.

ChatGPT/Gemini 스타일 테마. rx.color() 기반으로 다크/라이트 모드 자동 전환.
"""

import reflex as rx

# 색상 팔레트 - rx.color() 기반 (다크/라이트 자동 전환)
COLORS = {
    "sidebar_bg": rx.color("gray", 2),
    "sidebar_hover": rx.color("gray", 4),
    "sidebar_active": rx.color("gray", 5),
    "main_bg": rx.color("gray", 1),
    "user_bubble": rx.color("gray", 4),
    "ai_bubble": "transparent",
    "input_bg": rx.color("gray", 3),
    "input_border": rx.color("gray", 6),
    "text_primary": rx.color("gray", 12),
    "text_secondary": rx.color("gray", 10),
    "accent": rx.color("gray", 9),
    "accent_hover": rx.color("gray", 11),
    "border": rx.color("gray", 4),
    "tool_btn_bg": rx.color("gray", 4),
    "tool_btn_hover": rx.color("gray", 5),
    "category_text": rx.color("gray", 9),
    "scrollbar_thumb": rx.color("gray", 6),
}

# 간격 토큰
SPACING = {
    "sidebar_width": "260px",
    "input_bar_height": "100px",
    "message_max_width": "768px",
    "border_radius": "24px",
    "border_radius_sm": "8px",
    "border_radius_md": "16px",
    "padding_page": "1.5em",
    "padding_component": "1em",
}

# 타이포그래피
TYPOGRAPHY = {
    "font_family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "heading_size": "6",
    "body_size": "3",
    "small_size": "2",
}

# 글로벌 스타일
GLOBAL_STYLE = {
    "font_family": TYPOGRAPHY["font_family"],
    "::selection": {
        "background_color": rx.color("accent", 5),
    },
    "::-webkit-scrollbar": {
        "width": "6px",
    },
    "::-webkit-scrollbar-track": {
        "background": "transparent",
    },
    "::-webkit-scrollbar-thumb": {
        "background": str(COLORS["scrollbar_thumb"]),
        "border_radius": "3px",
    },
}

# 앱 테마
THEME = rx.theme(
    appearance="dark",
    has_background=True,
    radius="medium",
    accent_color="gray",
    gray_color="slate",
)
