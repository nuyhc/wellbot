import reflex as rx

config = rx.Config(
    app_name="wellbot",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)