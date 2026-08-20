# MQL5 Source Crawler

Desktop app (PySide6) để **tìm kiếm, tải và quản lý source code MQL5 công khai** trên MQL5.com
(Code Base: EA / Indicator / Script / Library, file `.mq5` `.mq4` `.mqh`).

Chạy trên Windows / Linux / macOS:

```bash
pip install -r requirements.txt
python main.py
```

## Nguyên tắc truy cập (quan trọng)

Tool **chỉ lấy source code mà MQL5.com công khai cho phép tải**, và **không bypass** CAPTCHA / login /
paywall / anti-bot / access control.

Kết quả kiểm tra `https://www.mql5.com/robots.txt` (thực tế, không phải giả định):

```text
Disallow: /*/search*              -> KHÔNG dùng endpoint search của site
Disallow: /*/code/viewcode/*      -> KHÔNG đọc source qua trang viewcode
Disallow: /*/code/download/*/     -> KHÔNG tải link download từng file
```

Vì vậy:

- Thay cho site search, tool duyệt các trang Code Base **được phép**:
  `https://www.mql5.com/en/code/mt5/experts` (và `indicators`, `scripts`, `libraries`, cùng `mt4/...`),
  rồi **lọc keyword phía client**.
- Nguồn tải chính là ZIP công khai của bài viết: `https://www.mql5.com/en/code/download/<id>.zip`
  (không bị disallow), giải nén và chỉ lấy `.mq5` / `.mq4` / `.mqh`.
- Mọi URL đều được kiểm tra qua robots.txt trước khi request; nếu bị chặn -> báo
  `Source unavailable / access not permitted` (status `NOT AVAILABLE`), không tìm cách vòng qua.

Selector HTML được xác minh trên trang thật:

| Trang | Selector |
| --- | --- |
| Listing | `div.code-tile`, `div.code-tile div.title a[href]`, `span.codeIcon[title]` |
| Detail | `h1`, `div.author-line a[href*='/users/']`, `dl.code-table`, `time[datetime]` |
| Attachment | `#codeAttachments a.attach-item__link[href]`, `a[href*='/code/download/'][href$='.zip']` |

## Tính năng

- **Search / Filter**: nhiều keyword (`Gold, XAUUSD, Scalping`), loại source (EA/Indicator/Script/Library),
  extension (MQ5/MQH), MT4/MT5, khoảng trang, số kết quả tối đa, sort latest/best.
- **Bảng kết quả**: `# / Name / Type / Author / MQ5 / Views / Rating / URL / Status`
  với trạng thái `READY, DOWNLOADED, SKIPPED, NOT AVAILABLE, DUPLICATE, ERROR`.
- **Download**: lưu vào `downloads/`, sanitize tên file
  (`Gold Scalping EA: XAU/USD.mq5` -> `Gold_Scalping_EA_XAU_USD.mq5`), trùng tên -> `_001`, `_002`.
- **SQLite** (`output/database.db`, table `mq5_sources`): source_id, name, author, type, source_url,
  file_url, filename, extension, crawl_time, download_time, status, sha256 (+ description, views,
  rating, votes, platform, local_path).
- **Duplicate detection** bằng SHA-256 nội dung source (unique index trên `sha256`).
- **Source viewer**: syntax highlighting MQL5, line number, search, find/replace, copy, save, open URL.
- **Static analysis**: lines/functions/inputs/includes, detect `Expert Advisor, CTrade, iMA, iRSI, iMACD,
  Buy/Sell, Grid, Martingale, ...` và phân loại chiến lược
  (`Trend Following, Scalping, Grid, Martingale, Breakout, Mean Reversion, News, Indicator Based, Unknown`).
  Đây chỉ là phân tích tĩnh, **không** kết luận source có lợi nhuận hay an toàn.
- **Queue + Start / Pause / Resume / Stop**, progress bar, log tab.
- **Rate limit**: delay (mặc định 2s) + jitter, timeout 30s, retry 3 lần, exponential backoff;
  gặp `HTTP 429` -> tự dừng crawl và cảnh báo (không cố vượt giới hạn).
- **Export**: MQ5 / CSV / Excel / JSON + copy database.
- **Logging**: console + file rotate `logs/crawler.log`.

## Chế độ CLI

```bash
python main.py --cli --keyword "Gold,XAUUSD" --type ea --platform mt5 --pages 1 3 --max 20 --delay 3 --export
```

| Tham số | Ý nghĩa |
| --- | --- |
| `--cli` | chạy không GUI |
| `--keyword` | keyword, phân cách bằng dấu phẩy (rỗng = lấy tất cả) |
| `--type` | `ea indicator script library` |
| `--platform` | `mt5 mt4` |
| `--pages FROM TO` | khoảng trang listing |
| `--max` | số kết quả tối đa |
| `--delay` | giây giữa 2 request |
| `--no-download` | chỉ lấy metadata |
| `--download-dir`, `--output-dir`, `--db` | đường dẫn output |
| `--export` | xuất CSV/JSON/XLSX/MQ5 sau khi chạy |

## Cấu trúc project

```text
mql5_source_crawler/
├── main.py                 # entry point (GUI + CLI)
├── gui/                    # main_window, search_widget, result_table, source_viewer, settings
├── crawler/                # crawler, search, downloader, parser, rate_limiter, http_client
├── analyzer/               # mq5_parser, detector, classifier
├── database/database.py    # SQLite (table mq5_sources)
├── exporter/exporter.py    # CSV / XLSX / JSON / MQ5 / DB
├── models/source.py        # SourceRecord, SourceType, Status
├── utils/                  # logger, hashing, filename, robots
├── downloads/  logs/  output/
├── tests/                  # pytest (38 test)
├── requirements.txt
└── pyproject.toml          # cấu hình ruff + pytest
```

Output sau khi export:

```text
output/
├── mq5/EA_xxx.mq5
├── metadata.csv
├── metadata.xlsx
├── metadata.json
└── database.db
```

## Test & lint

```bash
QT_QPA_PLATFORM=offscreen python -m pytest      # 38 passed
ruff check .
```

Test dùng HTML fixture và HTTP client giả lập nên **không gọi mạng**.

## Ghi chú

- Source trên MQL5 Code Base thuộc bản quyền tác giả tương ứng; hãy tuân thủ Terms of Use của MQL5.com
  khi sử dụng lại code.
- Nếu một bài viết không đính kèm `.mq5/.mqh` công khai, tool báo `NOT AVAILABLE` chứ không tự tìm cách lấy.
