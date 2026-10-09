"""Punto de entrada de Vercel: la funcion sin servidor que atiende /api/*. Todo lo demas (index.html,
css, js, fuentes) lo sirve la CDN de Vercel directo desde public/."""
from app.main import app  # noqa: F401  (Vercel busca la variable `app`)
