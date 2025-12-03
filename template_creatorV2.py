import os
import numpy as np
from moviepy import VideoClip, ImageClip, CompositeVideoClip

# --- GENEL AYARLAR ---
WIDTH = 1080
HEIGHT = 1920
TIMER_ANIM_DURATION = 13   # Bar'ın küçüldüğü süre
TOTAL_DURATION = 15 
FPS = 30
TIMER_HEIGHT = 20

# --- RENK PALETLERİ VERİTABANI (4 RENK) ---
# Renkler yukarıdan aşağıya (Koyu -> Açık) sırasıyla tanımlanmıştır.
PALETTES = [
    {
        "name": "Sunset_Fire",
        "colors": ["#C20A10", "#ED5A24", "#F7A01F", "#FEC412"]
    },
    {
        "name": "Violet_Mist",
        "colors": ["#2E0F48", "#59397A", "#A98FBF", "#E8D8F2"]
    },
    {
        "name": "Sky_Glow",
        "colors": ["#00062B", "#102E4A", "#6386AC", "#FFF7E3"]
    },
    {
        "name": "Royal_Green",
        "colors": ["#112F15", "#728D5A", "#EBF1B1", "#F1FFE4"]
    },
    {
        "name": "Luxury_Mocha",
        "colors": ["#342721", "#AA8163", "#DDC5A3", "#FBF1ED"]
    }
]

# --- YARDIMCI FONKSİYONLAR ---
def hex_to_rgb(hex_code):
    """HEX string (#RRGGBB) alır, (R, G, B) tuple döndürür."""
    hex_code = hex_code.lstrip('#')
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def lerp(a, b, t):
    """Linear interpolation between colors"""
    return a + (b - a) * t

# --- 1. FONKSİYON: 2 Renkli Basit Gradyan (Parça Oluşturucu) ---
def make_segment_gradient(w, h, top_color, bottom_color):
    """Belirli bir yükseklik için 2 renk arası dikey gradyan oluşturur."""
    yy, xx = np.mgrid[0:h, 0:w]
    ratio = yy / h
    
    # Renk kanallarını hesapla
    r = (top_color[0] * (1 - ratio) + bottom_color[0] * ratio).astype(np.uint8)
    g = (top_color[1] * (1 - ratio) + bottom_color[1] * ratio).astype(np.uint8)
    b = (top_color[2] * (1 - ratio) + bottom_color[2] * ratio).astype(np.uint8)
    
    return np.dstack((r, g, b))

# --- 2. FONKSİYON: 4 Renkli Multi-Stop Gradyan ---
def make_4color_gradient(w, h, colors_rgb):
    """
    Ekranı 3 bölüme ayırır ve 4 rengi birbirine bağlar:
    Bölüm 1: Renk 1 -> Renk 2
    Bölüm 2: Renk 2 -> Renk 3
    Bölüm 3: Renk 3 -> Renk 4
    """
    c1, c2, c3, c4 = colors_rgb
    
    # Yüksekliği 3 parçaya böl
    h1 = h // 3
    h2 = h // 3
    h3 = h - (h1 + h2) # Kalan pikselleri son parçaya ekle
    
    # 3 ayrı gradyan parçası oluştur
    grad1 = make_segment_gradient(w, h1, c1, c2)
    grad2 = make_segment_gradient(w, h2, c2, c3)
    grad3 = make_segment_gradient(w, h3, c3, c4)
    
    # Parçaları dikey olarak birleştir (stack)
    full_gradient = np.vstack((grad1, grad2, grad3))
    
    return full_gradient

# --- 3. FONKSİYON: Timer Mantığı (Aynı Kalıyor) ---
def get_color_by_ratio(ratio):
    c_green = (46, 204, 113)
    c_yellow = (255, 235, 59)
    c_orange = (255, 152, 0)
    c_red = (231, 76, 60)

    if ratio > 0.66:
        t = (1.0 - ratio) / 0.34
        c1, c2 = c_green, c_yellow
    elif ratio > 0.33:
        t = (0.66 - ratio) / 0.33
        c1, c2 = c_yellow, c_orange
    else:
        t = (0.33 - ratio) / 0.33
        c1, c2 = c_orange, c_red
    
    t = max(0.0, min(1.0, t))
    r = int(lerp(c1[0], c2[0], t))
    g = int(lerp(c1[1], c2[1], t))
    b = int(lerp(c1[2], c2[2], t))
    return (r, g, b)

def make_timer_frame(t, WIDTH):
    t_float = float(t)
    if t_float <= TIMER_ANIM_DURATION:
        remaining_ratio = (TIMER_ANIM_DURATION - t_float) / TIMER_ANIM_DURATION
    else:
        remaining_ratio = 0.0
    remaining_ratio = max(0, remaining_ratio)
    current_width = int(WIDTH * remaining_ratio)
    frame = np.zeros((TIMER_HEIGHT, WIDTH, 3), dtype=np.uint8)
    if current_width > 0:
        color = get_color_by_ratio(remaining_ratio)
        frame[:, WIDTH - current_width:] = color
    return frame

# --- ANA İŞLEM ---
def create_all_templates():
    print(f">>> 4 Renkli Toplu Template Oluşturucu Başlatıldı...")
    
    for pal in PALETTES:
        p_name = pal["name"]
        colors_hex = pal["colors"]
        
        # Hex listesini RGB listesine çevir
        colors_rgb = [hex_to_rgb(c) for c in colors_hex]
        
        output_filename = f"template_4color_{p_name}.mp4"
        
        print(f"\n--- {p_name} İŞLENİYOR ---")
        print(f"   Renkler: {colors_hex}")

        # A. 4 Renkli Arka Plan Klibi
        print("   Arka plan gradyanı oluşturuluyor...")
        bg_frame = make_4color_gradient(WIDTH, HEIGHT, colors_rgb)
        bg_clip = ImageClip(bg_frame).with_duration(TOTAL_DURATION)

        # B. Timer Klibi
        timer_clip = VideoClip(is_mask=False)
        timer_clip.frame_function = lambda t: make_timer_frame(t, WIDTH)
        timer_clip.make_frame = timer_clip.frame_function
        timer_clip.size = (WIDTH, TIMER_HEIGHT) 
        timer_clip = timer_clip.with_duration(TOTAL_DURATION).with_position(("center", 800))

        # C. Birleştirme ve Kaydetme
        final_video = CompositeVideoClip([bg_clip, timer_clip], size=(WIDTH, HEIGHT))

        print(f"   Render ediliyor: {output_filename} ...")
        final_video.write_videofile(
            output_filename, 
            fps=FPS, 
            codec="libx264", 
            audio=False, 
            preset="ultrafast", 
            threads=4,
            logger="bar"
        )
        
    print("\n>>> TÜM VİDEOLAR BAŞARIYLA OLUŞTURULDU! 🎉")

if __name__ == "__main__":
    create_all_templates()