"""
Génère les icônes PWA icon-192.png et icon-512.png
dans le dossier meteo_saas/static/
"""
import os

try:
    from PIL import Image, ImageDraw
    PIL_DISPO = True
except ImportError:
    PIL_DISPO = False


def generer_icone_svg():
    """Retourne le SVG de l'icône Mah Météo."""
    return '''<svg xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 100 100">
      <rect width="100" height="100"
        fill="#2c3e50" rx="20"/>
      <circle cx="50" cy="38" r="20"
        fill="#FFB81C"/>
      <g stroke="#FFB81C" stroke-width="2.5"
         stroke-linecap="round">
        <line x1="50" y1="8" x2="50" y2="15"/>
        <line x1="50" y1="61" x2="50" y2="68"/>
        <line x1="80" y1="38" x2="73" y2="38"/>
        <line x1="27" y1="38" x2="20" y2="38"/>
        <line x1="70" y1="18" x2="65" y2="23"/>
        <line x1="35" y1="53" x2="30" y2="58"/>
      </g>
      <path d="M 22 62 Q 18 62 18 68
               Q 18 76 26 78 L 74 78
               Q 82 76 82 68
               Q 82 62 78 62"
        fill="#ecf0f1" opacity="0.9"/>
    </svg>'''


def creer_icone_png(taille, chemin_sortie):
    """Crée une icône PNG de la taille demandée."""
    if not PIL_DISPO:
        print(f"[ICONE] Pillow non disponible")
        print(f"[ICONE] Installer : pip install Pillow")
        return False

    img = Image.new('RGBA', (taille, taille),
                    (44, 62, 80, 255))
    draw = ImageDraw.Draw(img)

    # Fond arrondi
    draw.rounded_rectangle(
        [0, 0, taille - 1, taille - 1],
        radius=taille // 5,
        fill=(44, 62, 80, 255)
    )

    # Soleil
    cx, cy = taille // 2, int(taille * 0.38)
    r = int(taille * 0.20)
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        fill=(255, 184, 28, 255)
    )

    # Nuage simplifié
    cy_nuage = int(taille * 0.68)
    r_nuage = int(taille * 0.22)
    draw.ellipse(
        [cx - r_nuage, cy_nuage - r_nuage // 2,
         cx + r_nuage, cy_nuage + r_nuage // 2],
        fill=(236, 240, 241, 230)
    )

    os.makedirs(os.path.dirname(chemin_sortie),
                exist_ok=True)
    img.save(chemin_sortie, 'PNG')
    print(f"[ICONE] Généré : {chemin_sortie} ({taille}px)")
    return True


if __name__ == '__main__':
    static_dir = os.path.join(
        'meteo_saas', 'static'
    )
    creer_icone_png(
        192,
        os.path.join(static_dir, 'icon-192.png')
    )
    creer_icone_png(
        512,
        os.path.join(static_dir, 'icon-512.png')
    )
    print('[ICONE] Terminé')