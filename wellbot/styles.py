"""디자인 토큰 및 테마 설정."""

import reflex as rx

# 색상 팔레트
COLORS = {
    "sidebar_bg": rx.color("gray", 2),
    "main_bg": rx.color("gray", 1),
    "user_bubble": rx.color("accent", 4),
    "ai_bubble": rx.color("gray", 3),
    "input_bg": rx.color("gray", 3),
    "input_border": rx.color("gray", 6),
    "text_primary": rx.color("gray", 12),
    "text_secondary": rx.color("gray", 11),
    "accent": rx.color("accent", 9),
    "accent_hover": rx.color("accent", 10),
    "border": rx.color("gray", 5),
    "toast_error": rx.color("red", 9),
}

# 간격 토큰
SPACING = {
    "sidebar_width": "280px",
    "input_bar_height": "80px",
    "message_max_width": "720px",
    "border_radius": "12px",
    "border_radius_sm": "8px",
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
}

# 앱 테마
THEME = rx.theme(
    appearance="dark",
    has_background=True,
    radius="medium",
    accent_color="blue",
    gray_color="slate",
)
