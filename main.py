from fastapi import FastAPI, UploadFile, File
import numpy as np
import cv2
import zxingcpp
import httpx

from settings import settings

app = FastAPI()

def decode_zxing(img_bgr: np.ndarray) -> str | None:
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    results = zxingcpp.read_barcodes(img_rgb)
    if results:
        return results[0].text
    return None

def preprocess_variants(img_bgr: np.ndarray):
    h, w = img_bgr.shape[:2]
    yield img_bgr

    scale = 1.6 if max(h, w) < 1400 else 1.0
    if scale != 1.0:
        up = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        yield up
    else:
        up = img_bgr

    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    sharp = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.6, sharp, -0.6, 0)
    yield cv2.cvtColor(sharp, cv2.COLOR_GRAY2BGR)

    thr = cv2.adaptiveThreshold(
        sharp, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 5
    )
    yield cv2.cvtColor(thr, cv2.COLOR_GRAY2BGR)

    inv = cv2.bitwise_not(thr)
    yield cv2.cvtColor(inv, cv2.COLOR_GRAY2BGR)

def crop_candidates(img_bgr: np.ndarray):
    h, w = img_bgr.shape[:2]
    yield img_bgr
    yield img_bgr[int(h * 0.45):h, 0:w]
    y1, y2 = int(h * 0.15), int(h * 0.85)
    x1, x2 = int(w * 0.10), int(w * 0.90)
    yield img_bgr[y1:y2, x1:x2]

async def upload_original_file(
    original_bytes: bytes,
    filename: str,
    content_type: str | None
) -> str | None:
    """
    Faz POST multipart/form-data.
    Retorna file_id se OK e existir no JSON.
    Se falhar, retorna None.
    """
    headers = {"x-api-key": settings.upload_x_api_key}
    timeout = httpx.Timeout(settings.upload_timeout_seconds)

    # fallback de content-type
    ct = content_type or "application/octet-stream"

    files = {
        # ajuste o nome do campo se a API exigir outro;
        # aqui assumo "file" (bem comum)
        "file": (filename or "upload.bin", original_bytes, ct)
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(settings.upload_url, headers=headers, files=files)

        if resp.status_code >= 200 and resp.status_code < 300:
            # tenta JSON
            try:
                payload = resp.json()
            except Exception:
                return None
            file_id = payload.get("file_id")
            return file_id if isinstance(file_id, str) and file_id.strip() else None

        return None
    except Exception:
        return None

@app.post("/api/qr/decode")
async def decode_qr(image: UploadFile = File(...)):
    try:
        original_bytes = await image.read()

        arr = np.frombuffer(original_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return {"success": False, "message": "Imagem inválida ou formato não suportado.", "file_id": None}

        rotations = [0, 90, 180, 270]
        for rot in rotations:
            if rot == 0:
                rotated = img
            elif rot == 90:
                rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            elif rot == 180:
                rotated = cv2.rotate(img, cv2.ROTATE_180)
            else:
                rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

            for crop in crop_candidates(rotated):
                for variant in preprocess_variants(crop):
                    text = decode_zxing(variant)
                    if text:
                        # remove as 2 primeiras letras
                        cleaned_text = text[2:] if len(text) > 2 else ""

                        file_id = await upload_original_file(
                            original_bytes=original_bytes,
                            filename=image.filename or "upload.jpg",
                            content_type=image.content_type
                        )

                        return {
                            "success": True,
                            "data": cleaned_text,
                            "file_id": file_id  # None se falhar
                        }

        return {"success": False, "message": "QR não encontrado.", "file_id": None}

    except Exception as e:
        return {"success": False, "message": str(e), "file_id": None}