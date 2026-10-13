# Queens Twelve — Website N hậu 12 × 12

Website tiếng Việt hoàn chỉnh: bàn cờ 2D tương tác, nhập `input.txt`, điểm trực tiếp, nộp lời giải lên server, bảng xếp hạng công khai, xem bàn cờ/tác giả từng bài, tải lời giải và chia sẻ liên kết.

## Chạy trên máy

Cần Python 3.10 trở lên (khuyến nghị 3.13).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Windows: dùng `.venv\Scripts\activate` thay cho lệnh `source`.
Mở http://127.0.0.1:8000. Dữ liệu mặc định ở `data/queens.db`; thư mục tự được tạo. Đổi cổng bằng biến `PORT`.

## Đưa lên Render

Đã có `render.yaml` để Render tạo Web Service và persistent disk. Không cần build frontend hay Node.js.

1. Giải nén source và đưa **nội dung thư mục queens12** lên một GitHub/GitLab repository của bạn. `app.py`, `requirements.txt`, `render.yaml` phải nằm ở gốc repository.
2. Vào Render Dashboard → **New → Blueprint** → kết nối repository đó.
3. Render đọc `render.yaml`. Kiểm tra cấu hình và chi phí trong Dashboard rồi triển khai.
4. Mở địa chỉ `https://<tên-service>.onrender.com` Render cấp. Những người vào cùng URL sẽ thấy chung bảng xếp hạng. Danh sách tự cập nhật mỗi 30 giây khi tab đang hiển thị, hoặc bấm ↻.

**Lưu ý lưu trữ:** Blueprint dùng gói `starter` có trả phí và persistent disk 1 GB gắn tại `/var/data`. SQLite nằm ở `/var/data/queens.db`, nên giữ lại qua deploy/restart. Render Free không hỗ trợ persistent disk; đừng chuyển cấu hình này sang Free nếu muốn giữ dữ liệu. Nếu cần chạy miễn phí lâu dài, phải đổi phần database sang một dịch vụ lưu trữ bên ngoài; source hiện tại dùng SQLite.

Nếu tạo **Web Service** thủ công, dùng:

| Mục | Giá trị |
|---|---|
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 --access-logfile -` |
| Health check | `/healthz` |
| `PYTHON_VERSION` | `3.13.5` |
| `DATABASE_PATH` | `/var/data/queens.db` |
| `TRUST_RENDER_PROXY` | `1` (chỉ bật khi nằm sau proxy Render) |
| Persistent disk | mount `/var/data`, 1 GB |

Chỉ chạy 1 instance với SQLite/persistent disk. Render tự cấp HTTPS. Không dùng `python app.py` làm lệnh production.

Tài liệu chính thức, đã đối chiếu khi tạo source:
- https://render.com/docs/deploy-flask
- https://render.com/docs/disks
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free

## Quy tắc input và chấm điểm

- N cố định bằng 12, bàn cờ gồm 144 ô.
- Góc trên trái là `(1,1)`. `x` là **cột**, tăng sang phải; `y` là **hàng**, tăng xuống dưới.
- Khi nộp bài: đúng 12 quân trên 12 ô khác nhau; mỗi tọa độ là số nguyên 1…12. Không bắt buộc mỗi hàng/cột có một quân: các cấu hình xung đột vẫn được nhận và chấm điểm.
- File `.txt` UTF-8, tối đa 4 KB, chứa **24 số**. Cho phép phân tách bằng khoảng trắng, tab, xuống dòng hoặc dấu phẩy. Không có số N ở đầu, không có dấu ngoặc hay phần chú thích.
- Ví dụ `1 1 2 2 ... 12 12` (thay dấu `...` bằng các cặp số thực) là 12 quân trên đường chéo, **0 điểm**.
- Ví dụ 8 cặp trong yêu cầu ban đầu biểu diễn đúng 8 quân, nhưng chưa đủ để nộp cho N=12.
- **Điểm = số quân hậu không bị bất kỳ quân hậu nào khác tấn công.** Cùng hàng, cùng cột, hoặc `abs(x1-x2) == abs(y1-y2)` là tấn công. Mỗi quân an toàn được 1 điểm; tối đa 12 điểm. Đây không phải kích thước tập con hậu không tấn công lớn nhất và cũng không phải số cặp không tấn công.
- Cặp tấn công chỉ đếm một lần. 12 hậu trên đường chéo có 66 cặp, 0 quân an toàn.
- Server tự tính điểm, không tin `score` do client gửi. Giao diện cho phép xếp 0–12 quân nhưng nút nộp chỉ mở khi đủ 12 quân.
- Xếp hạng theo điểm giảm dần, thời điểm nộp tăng dần; ID làm tiêu chí cuối khi trùng thời gian. Mỗi bài nộp có hạng riêng.

Có sẵn `examples/input.txt` (lời giải 12 điểm) và `examples/diagonal.txt` (0 điểm) để kiểm tra. Database bắt đầu rỗng, không có bài nộp giả.

## Chức năng

- Bấm để đặt/bỏ quân; hỗ trợ phím mũi tên và Enter/Space trên bàn cờ.
- Tô màu hậu bị tấn công, điểm tức thời, số cặp xung đột.
- Hoàn tác tối đa 100 bước, xóa bàn, lưu nháp tại trình duyệt.
- Nhập file bằng nút chọn hoặc kéo thả; server xác thực trước khi thay bàn cờ.
- Tên tác giả 2–40 ký tự, tên lời giải 2–80 ký tự.
- Xem lời giải công khai: bàn cờ lớn, tọa độ, tác giả, ngày nộp, điểm; tải lại `input.txt`, sao chép URL.
- Tìm kiếm tác giả/tên bài, phân trang 12 bài/trang, giữ hạng toàn cục khi tìm kiếm.
- Tối thiểu 10 giây giữa các lần nộp từ cùng địa chỉ IP; lưu giới hạn trong database, hoạt động qua restart. Người chung mạng có thể cùng chịu giới hạn này.
- SQL có tham số, giới hạn kích thước request, CSP, hiển thị tên bằng `textContent` để tránh HTML/script do người nộp chèn vào.

Tên tác giả là **tên tự khai**, không phải tài khoản đã xác thực. Bản này không có đăng nhập, xác minh chủ sở hữu, chỉnh sửa/xóa bài qua giao diện hay kiểm duyệt. Mỗi bài nộp tạo một bản ghi mới. Phù hợp bài tập/thử thách cộng đồng quy mô nhỏ; giới hạn IP không thay thế hệ thống chống spam quy mô lớn.

## Kiểm tra

Từ thư mục source, sau khi cài requirements:

```bash
python -m unittest discover -s tests -v
```

Test bao gồm điểm 12, đường chéo 0 điểm, cặp tấn công, input sai/trùng ô/ngoài biên, điểm giả, lưu dữ liệu qua khởi tạo lại ứng dụng, tìm kiếm/phân trang/thứ hạng, giới hạn nộp đồng thời và giới hạn dung lượng.

## API

| Endpoint | Mục đích |
|---|---|
| `GET /healthz` | Kiểm tra ứng dụng/database |
| `POST /api/parse` | JSON `{ "text": "1 1 ..." }`, kiểm tra đủ 12 tọa độ và trả kết quả chấm |
| `POST /api/submissions` | JSON `{ "author": "Tên", "title": "Bài", "positions": [[1,1], ...] }` (hoặc `text` thay `positions`) |
| `GET /api/submissions?page=1&q=...` | Bảng xếp hạng, tổng số, thống kê |
| `GET /api/submissions/<id>` | Xem một bài và hạng toàn cục |

API dùng JSON cùng origin, không cần token. Tên/tọa độ là dữ liệu công khai khi nộp; không nhập thông tin riêng tư vào tên bài.

## Cấu trúc

```text
app.py                 Server, API, SQLite, giới hạn nộp
queens.py              Kiểm tra tọa độ, đọc file, chấm điểm
static/index.html      Giao diện tiếng Việt
static/style.css       Responsive desktop/mobile
static/app.js          Bàn cờ, upload, nộp bài, bảng rank
static/crown.svg        Biểu tượng
examples/              Input mẫu
requirements.txt       Dependency Python
render.yaml            Cấu hình Render + persistent disk
tests/test_app.py     Kiểm thử quy tắc và API
```

Sao lưu database trước khi xóa disk/service. Nếu sao lưu trong lúc server hoạt động, dùng SQLite backup API thay vì chỉ copy file `.db` (WAL có thể chứa giao dịch chưa checkpoint).
