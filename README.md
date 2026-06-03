# AI Ecotourism Assistant MVP

Flow demo:

```text
QR Scan → Landing → Video giới thiệu → Hoạt động nổi bật → AI Chatbot → Cảm ơn
```

## 1. Chạy Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 2. Chạy Frontend

```bash
cd frontend
npm install
npm run dev
```

Mở: `http://localhost:5173`

## 3. QR Demo

Bấm nút **Quét QR demo**. Mã QR mẫu là:

```text
ECO_NUI_BA_DEN_001
```

## 4. API chính

- `POST /api/qr/scan`
- `GET /api/destinations/{destination_id}`
- `POST /api/chat`
- `POST /api/rag/chat`
- `GET /api/rag/status`
- `POST /api/survey`
- `GET /api/survey/results`

## 5. RAG + Claude

Backend dùng RAG từ file Excel, embedding bằng `sentence-transformers/all-MiniLM-L6-v2`.
MiniLM gốc trả vector 384 chiều; hệ thống fit về `RAG_EMBEDDING_DIM=348` theo cấu hình hiện tại.

```powershell
$env:ANTHROPIC_API_KEY="your_api_key"
$env:ANTHROPIC_MODEL="claude-haiku-4-5"
$env:ANTHROPIC_BASE_URL="https://api.huyztech.store/v1/ai"
$env:ANTHROPIC_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
$env:RAG_EMBEDDING_DIM="348"
uvicorn app.main:app --reload --port 8001
```

Nếu chưa có `ANTHROPIC_API_KEY`, API vẫn retrieval bằng MiniLM và trả fallback answer từ context nội bộ.

Đây là bản MVP phục vụ trải nghiệm AI Ecotourism Assistant 3-5 phút, không cần đăng nhập,
không cần booking/thanh toán.
