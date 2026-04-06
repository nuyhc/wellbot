import os

import reflex as rx
from dotenv import load_dotenv

load_dotenv()

db_url = (
    f"mysql+pymysql://{os.getenv('DB_USER', 'wellbot')}:{os.getenv('DB_PASSWORD', '')}"
    f"@{os.getenv('DB_HOST', '127.0.0.1')}:{os.getenv('DB_PORT', '3306')}"
    f"/{os.getenv('DB_NAME', 'wellbot_db')}"
)

config = rx.Config(
    app_name="wellbot",
    db_url=db_url,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)