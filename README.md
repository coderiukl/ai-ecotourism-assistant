# AI Ecotourism Assistant

Chatbot du lịch Núi Bà Đen với frontend React/Vite, backend FastAPI, dữ liệu Supabase/Excel và RAG bằng ChromaDB.

## Bật tìm kiếm web

Chatbot ưu tiên dữ liệu nội bộ và nguồn chính thức Sun World. Với mọi câu hỏi tư
vấn có nội dung, chatbot tự tìm thêm trên web, tổng hợp câu trả lời và dẫn nguồn;
người dùng không cần yêu cầu tìm kiếm. Các lượt xã giao ngắn như chào hỏi hoặc cảm
ơn được bỏ qua để giảm độ trễ. Để bật chế độ này, thêm khóa Tavily vào
`backend/.env`:

```env
WEB_SEARCH_ENABLED=true
WEB_SEARCH_PROVIDER=tavily
WEB_SEARCH_API_KEY=tvly-...
```

Khởi động lại backend rồi kiểm tra `GET /api/status`. Khi
`web_search.configured` là `true`, câu trả lời dùng dữ liệu web sẽ có ký hiệu
`[1]`, `[2]` và các đường dẫn tương ứng trong phần **Nguồn tham khảo**.

### Kho kiến thức web

Khi `DATABASE_URL` được cấu hình, các nguồn chatbot tìm thấy được tự động lưu vào
bảng `web_knowledge` trong PostgreSQL. Những câu hỏi sau sẽ dùng đồng thời nguồn
mới tìm, nguồn liên quan đã lưu và dữ liệu RAG nội bộ. Nguồn mới luôn được ưu tiên
cho thông tin dễ thay đổi.

Mặc định hệ thống giữ nguồn đã lưu trong phạm vi truy xuất 90 ngày và lấy tối đa
4 nguồn cũ cho mỗi câu hỏi. Có thể điều chỉnh bằng:

```env
WEB_KNOWLEDGE_RETENTION_DAYS=90
WEB_KNOWLEDGE_MAX_CONTEXTS=4
```

`GET /api/status` trả về `web_knowledge.documents` để theo dõi số nguồn đã lưu.
