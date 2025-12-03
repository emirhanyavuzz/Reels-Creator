import os
import csv
import numpy as np
from functools import lru_cache
from moviepy import VideoClip
from moviepy.video.io.ffmpeg_writer import ffmpeg_write_video
from moviepy.video.io.ffmpeg_tools import ffmpeg_merge_video_audio
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from PIL import Image, ImageDraw, ImageFont
import gc # Garbage collector importu eklendi (RAM temizliği için)

# --- AYARLAR ---
# Tek dosya yerine liste kullanıyoruz
#TEMPLATE_FILES = ["templatecyan.mp4", "templatedarkblue.mp4", "templatesunset.mp4"]
TEMPLATE_FILES = ["template_4color_Luxury_Mocha.mp4", "template_4color_Royal_Green.mp4", "template_4color_Sky_Glow.mp4", "template_4color_Sunset_Fire.mp4", "template_4color_Violet_Mist.mp4"]

OUTPUT_DIR = "quiz_videolari"
WIDTH = 1080
HEIGHT = 1920
HIGHLIGHT_DURATION = 2.0  
FPS = 24

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Renkler
TEXT_COLOR = (240, 248, 255)
OPTION_BG = (60, 70, 100)    # Standart kutu rengi
CORRECT_BG = (46, 204, 113)  # Doğru cevap rengi (Yeşil)

def find_font_path():
    font_paths = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return fp
    return None

FONT_PATH = find_font_path()
if FONT_PATH is None:
    raise RuntimeError("Font bulunamadı! Sistem fontlarından birini yükleyin veya FONT_PATH verin.")

FONT_BIG  = ImageFont.truetype(FONT_PATH, size=80)
FONT_MED  = ImageFont.truetype(FONT_PATH, size=60)
FONT_SMALL = ImageFont.truetype(FONT_PATH, size=40)

def load_questions_from_csv(csv_file):
    sorular = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sorular.append({
                "id": row["id"],
                "soru": row["soru"],
                "siklar": [row["sik1"], row["sik2"], row["sik3"], row["sik4"]],
                "dogruCevap": [row["dogruCevap"]]
            })
    return sorular

def pil_to_rgb_alpha(pil_img):
    """PIL RGBA -> (rgb_uint8, alpha_float_0_1)"""
    arr = np.array(pil_img)  # H x W x 4
    if arr.shape[2] == 4:
        rgb = arr[:, :, :3].astype(np.uint8)
        alpha = arr[:, :, 3].astype(np.float32) / 255.0
    else:
        rgb = arr[:, :, :3].astype(np.uint8)
        alpha = np.ones((arr.shape[0], arr.shape[1]), dtype=np.float32)
    return rgb, alpha

@lru_cache(maxsize=256)
def render_text_cached(soru_id, soru_text, sik1, sik2, sik3, sik4, highlight_idx):
    """Cache'lenmiş text layer üretir. highlight_idx=None veya 0-3"""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    question_box = (100, 300, WIDTH - 200, 400)
    draw_text_autofit(draw, soru_text, question_box, max_font_size=80, color=TEXT_COLOR)

    siklar = [sik1, sik2, sik3, sik4]
    positions = [
        (150, 950), (600, 950),
        (150, 1200), (600, 1200)
    ]
    box_w, box_h = 400, 150

    for i, sik in enumerate(siklar):
        x, y = positions[i]
        current_bg = OPTION_BG
        if highlight_idx is not None and i == highlight_idx:
            current_bg = CORRECT_BG
        
        draw.rounded_rectangle([x, y, x+box_w, y+box_h], radius=20, fill=current_bg)
        padding = 20
        text_box = (x + padding, y + padding, box_w - (2*padding), box_h - (2*padding))
        draw_text_autofit(draw, sik, text_box, max_font_size=60, color=TEXT_COLOR, min_font_size=30)

    rgb, alpha = pil_to_rgb_alpha(img)
    return (rgb.tobytes(), alpha.tobytes(), rgb.shape, alpha.shape)

def unpack_cached_image(cached):
    rgb_bytes, alpha_bytes, rgb_shape, alpha_shape = cached
    rgb = np.frombuffer(rgb_bytes, dtype=np.uint8).reshape(rgb_shape)
    alpha = np.frombuffer(alpha_bytes, dtype=np.float32).reshape(alpha_shape)
    return rgb, alpha

def draw_text_autofit(draw, text, box, max_font_size, color=(255,255,255), min_font_size=20):
    box_x, box_y, box_w, box_h = box
    current_font_size = max_font_size

    while current_font_size >= min_font_size:
        try:
            font = ImageFont.truetype(FONT_PATH, size=current_font_size)
        except:
            font = ImageFont.load_default()

        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                w = draw.textlength(test_line, font=font)
            except:
                w = draw.textbbox((0,0), test_line, font=font)[2]

            if w <= box_w:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))

        ascent, descent = font.getmetrics() if hasattr(font, "getmetrics") else (int(current_font_size*0.8), int(current_font_size*0.2))
        line_height = ascent + descent + 8
        total_text_height = line_height * len(lines)

        if total_text_height <= box_h:
            start_y = box_y + (box_h - total_text_height) // 2
            for i, line in enumerate(lines):
                try:
                    w_line = draw.textlength(line, font=font)
                except:
                    w_line = draw.textbbox((0,0), line, font=font)[2]
                x_pos = box_x + (box_w - w_line) // 2
                y_pos = start_y + (i * line_height)
                draw.text((x_pos, y_pos), line, font=font, fill=color)
            return
        current_font_size -= 2

    font = ImageFont.truetype(FONT_PATH, size=min_font_size) if FONT_PATH else ImageFont.load_default()
    draw.text((box_x, box_y), text, font=font, fill=color)

def get_correct_option_index(soru_data):
    answer_key = soru_data["dogruCevap"]
    if isinstance(answer_key, list):
        answer_key = answer_key[0]
    answer_key = answer_key.upper().strip()
    if answer_key.startswith("A"): return 0
    if answer_key.startswith("B"): return 1
    if answer_key.startswith("C"): return 2
    if answer_key.startswith("D"): return 3
    return -1

# --- MAIN optimized renderer (Updated for Multi-Template) ---
def main():
    # Template kontrolü
    for t_file in TEMPLATE_FILES:
        if not os.path.exists(t_file):
            print(f"HATA: '{t_file}' bulunamadı! Lütfen tüm template dosyalarını oluşturun.")
            return

    sorular = load_questions_from_csv("sorular.csv")
    if not sorular:
        print("sorular.csv boş veya bulunamadı.")
        return

    # Soruları Template'lere göre grupla (Modülo 3 mantığı)
    # 0. index -> Template 1, 1. index -> Template 2, 2. index -> Template 3
    batch_dict = {0: [], 1: [], 2: []}
    for i, soru in enumerate(sorular):
        batch_dict[i % 5].append(soru)

    print(">>> Metin katmanları cache'e alınıyor (Ön hazırlık)...")
    # Cache işlemini toplu yapıyoruz
    for soru in sorular:
        correct_idx = get_correct_option_index(soru)
        render_text_cached(soru['id'], soru['soru'], soru['siklar'][0], soru['siklar'][1],
                           soru['siklar'][2], soru['siklar'][3], None)
        render_text_cached(soru['id'], soru['soru'], soru['siklar'][0], soru['siklar'][1],
                           soru['siklar'][2], soru['siklar'][3], correct_idx)

    # --- ANA DÖNGÜ: Template başına işleme ---
    # Her template'i RAM'e yükleyip, ona ait soruları bitirip, RAM'i boşaltacağız.
    for t_idx, template_file in enumerate(TEMPLATE_FILES):
        current_batch = batch_dict[t_idx]
        
        if not current_batch:
            continue # Bu template'e düşen soru yoksa geç

        print(f"\n>>> [{t_idx+1}/3] Template Yükleniyor: {template_file}")
        
        base_clip = VideoFileClip(template_file)
        total_duration = base_clip.duration
        highlight_start_time = total_duration - HIGHLIGHT_DURATION
        
        # Kareleri RAM'e al (Hız için)
        base_frames = []
        for frame in base_clip.iter_frames(fps=FPS, dtype="uint8"):
            base_frames.append(frame)
        
        # FFmpeg bağlantılarını temizle
        base_clip.reader.close()
        base_clip.audio = None
        del base_clip # Nesneyi sil

        print(f">>> '{template_file}' ile {len(current_batch)} adet soru işleniyor...")

        for soru in current_batch:
            qid = soru['id']
            print(f"   -> İşleniyor: {qid} (Kullanılan: {template_file})")
            correct_idx = get_correct_option_index(soru)

            # Retrieve cached images
            cached_normal = render_text_cached(soru['id'], soru['soru'], soru['siklar'][0], soru['siklar'][1],
                                               soru['siklar'][2], soru['siklar'][3], None)
            cached_high = render_text_cached(soru['id'], soru['soru'], soru['siklar'][0], soru['siklar'][1],
                                             soru['siklar'][2], soru['siklar'][3], correct_idx)

            overlay_normal_rgb, overlay_normal_alpha = unpack_cached_image(cached_normal)
            overlay_high_rgb, overlay_high_alpha = unpack_cached_image(cached_high)

            alpha_norm_normal = overlay_normal_alpha.astype(np.float32)[..., None]
            alpha_norm_high = overlay_high_alpha.astype(np.float32)[..., None]

            # Closure (base_frames'i buradan okur)
            def make_frame(t):
                frame_idx = int(min(len(base_frames)-1, max(0, round(t * FPS))))
                base = base_frames[frame_idx].astype(np.float32)

                if t < highlight_start_time:
                    ov_rgb = overlay_normal_rgb.astype(np.float32)
                    ov_alpha = alpha_norm_normal
                else:
                    ov_rgb = overlay_high_rgb.astype(np.float32)
                    ov_alpha = alpha_norm_high

                comp = (ov_alpha * ov_rgb) + ((1.0 - ov_alpha) * base)
                return np.clip(comp, 0, 255).astype(np.uint8)

            clip = VideoClip(make_frame, duration=total_duration)
            output_path = os.path.join(OUTPUT_DIR, f"{qid}.mp4")

            clip.write_videofile(
                output_path,
                fps=FPS,
                codec="libx264",
                audio=False,
                preset="veryfast",
                ffmpeg_params=["-tune", "zerolatency", "-crf", "23"],
                threads=8,
                logger=None
            )
        
        # TEMPLATE BİTTİ, RAM TEMİZLİĞİ
        print(f">>> '{template_file}' grubu tamamlandı. RAM temizleniyor...")
        del base_frames
        gc.collect() # Çöp toplayıcıyı zorla çalıştır

    print("\n>>> Tüm işlemler başarıyla bitti.")

if __name__ == "__main__":
    main()