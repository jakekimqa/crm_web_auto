"""테스트용 사진 10장 생성 (각기 다른 MB 크기, 이미지에 크기 텍스트 표시)"""

import os
import io
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# 목표 크기 (MB)
TARGET_SIZES_MB = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 4.9]


def create_photo(target_mb: float, index: int):
    """목표 MB 크기의 JPEG 이미지를 생성하고, 이미지 중앙에 크기 텍스트를 표시"""
    target_bytes = int(target_mb * 1024 * 1024)
    label = f"{target_mb}MB"
    filename = f"test_photo_{label.replace('.', '_')}.jpg"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # 큰 이미지일수록 해상도를 높여서 목표 크기에 도달
    base_size = int(800 + (target_mb * 600))
    img = Image.new("RGB", (base_size, base_size), color=(30 + index * 20, 80 + index * 15, 150 - index * 10))
    draw = ImageDraw.Draw(img)

    # 텍스트 그리기
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", size=max(80, base_size // 8))
    except (OSError, IOError):
        font = ImageFont.load_default()

    text = f"{label}\n({index + 1}/10)"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (base_size - text_w) // 2
    y = (base_size - text_h) // 2
    # 그림자
    draw.text((x + 3, y + 3), text, fill=(0, 0, 0), font=font, align="center")
    draw.text((x, y), text, fill=(255, 255, 255), font=font, align="center")

    # 노이즈 패턴 추가 (JPEG 압축 후에도 크기를 유지하기 위해)
    import random
    random.seed(index)
    for _ in range(base_size * 10):
        rx, ry = random.randint(0, base_size - 1), random.randint(0, base_size - 1)
        r, g, b = img.getpixel((rx, ry))
        noise = random.randint(-30, 30)
        img.putpixel((rx, ry), (max(0, min(255, r + noise)), max(0, min(255, g + noise)), max(0, min(255, b + noise))))

    # 해상도를 키워가며 목표 크기 * 0.9 이상이 되도록 조정
    while True:
        # quality를 내려가며 목표 크기 이하인 최대 quality 찾기
        best_quality = None
        for q in range(95, 10, -1):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=q)
            if buf.tell() <= target_bytes:
                best_quality = q
                break

        if best_quality is not None:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=best_quality)
            if buf.tell() >= target_bytes * 0.9:
                data = buf.getvalue()
                break

        # 아직 목표의 90%에 못 미치면 해상도를 키워서 재시도
        new_size = int(img.width * 1.3)
        img = img.resize((new_size, new_size), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", size=max(80, new_size // 8))
        except (OSError, IOError):
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (new_size - text_w) // 2
        y = (new_size - text_h) // 2
        draw.text((x + 3, y + 3), text, fill=(0, 0, 0), font=font, align="center")
        draw.text((x, y), text, fill=(255, 255, 255), font=font, align="center")

    with open(filepath, "wb") as f:
        f.write(data)

    actual_size = os.path.getsize(filepath)
    print(f"  {filename}: {actual_size / 1024 / 1024:.2f} MB")
    return filename


if __name__ == "__main__":
    print("테스트 사진 생성 시작...")
    filenames = []
    for i, size_mb in enumerate(TARGET_SIZES_MB):
        name = create_photo(size_mb, i)
        filenames.append(name)
    print(f"\n완료! {len(filenames)}장 생성됨")
    print("파일 목록:")
    for f in filenames:
        print(f"  - {f}")
