# Làm phim AI tiếng Việt bằng Claude + Seedance 2.5 API

Get your Seedance 2.5 API Key on BytePlus: https://bit.ly/3Vqzy7X

Bộ tài liệu đi kèm video của Holetex: thiết lập nhân vật, mẫu storyboard / scene sheet, file cấu hình MCP và script hàng đợi sản xuất. Claude viết phim, Seedance 2.5 sinh từng cảnh, script tự gửi task, theo dõi trạng thái và tải video về máy.

## Cần có

- Windows, Claude app (desktop)
- Seedance 2.5 Resource Plan + API key trên BytePlus ModelArk: https://bit.ly/3Vqzy7X
- Trong ModelArk → Model activation: bật **Seedance 2.5** và **Seedream 5.0 Pro**

## Cài đặt (3 bước)

1. Double-click `1-cai-dat.bat` (tự cài uv, tải ark-mcp của BytePlus, cài thư viện).
2. Mở `ark\.env`, dán API key vào dòng `BYTEPLUS_MODELARK_API_KEY=`.
3. Claude app → Settings → Developer → Edit Config → dán khối trong `cau-hinh\claude_desktop_config.example.json`, sửa `C:\DUONG\DAN\TOI` thành đường dẫn thư mục này → khởi động lại Claude app.

## Làm phim

| Bước | Làm gì | File |
|---|---|---|
| 1 | Sinh ảnh tham chiếu nhân vật + bối cảnh | `2-tao-anh-nhan-vat.bat` (prompt trong `nhan-vat\prompt-anh.json`) |
| 2 | Nhờ Claude viết phim → scene sheet | mẫu: `mau-scene-sheet.json`, ví dụ: `queue\ep01.json` |
| 3 | Chạy hàng đợi: gửi task, polling, tự tải về `output\` | `3-chay-hang-doi.bat` |
| 4 | Thêm tập mới khi đang chạy: copy file vào `queue\` | ví dụ: `tap-tiep-theo\ep02.json`, `ep03.json` |

Token mỗi cảnh ghi ở `output\usage.csv`. Giá tham khảo tại thời điểm làm video: 480p ≈ 9.700 token/giây, 1080p ≈ 48.600 token/giây.

## Lưu ý

- `queue\ep01.json` là Tập 1 ở **1080p (~2,9 triệu token)**. Muốn thử trước thì đổi `"resolution": "480p"` (~0,6 triệu token).

- Link video kết quả chỉ sống 24 giờ, tối đa 100 lượt tải → script tự tải ngay khi xong.
- Cảnh đã sinh vẫn tính token kể cả khi không dùng → test 480p trước, ưng rồi mới lên 1080p.
- Seedance 2.5 tối đa 1080p.
- Ảnh tham chiếu: script gửi file trong máy dạng base64; nếu dùng URL thì phải là URL công khai (ví dụ BytePlus TOS).
- Không chia sẻ file `ark\.env` (chứa API key).
