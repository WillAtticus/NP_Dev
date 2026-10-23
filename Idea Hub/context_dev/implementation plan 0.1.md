# NeuroPulse Implementation Plan 0.1

**Mục đích:** Bàn giao backlog có thể thực hiện cho AI agent/developer tiếp theo. Tài liệu này đối chiếu master spec, tài liệu `docs/`, handoff/drift log, các yêu cầu trong chat và trạng thái mã được ghi nhận gần nhất. Đây là kế hoạch, không phải xác nhận rằng các chức năng đã được kiểm thử hoặc app đã sẵn sàng dùng với người tham gia.

**Nguồn ưu tiên:** `Idea Hub/NEUROPULSE_ANTIGRAVITY_MVP_MASTER_SPEC.md` (phiên bản mới nhất) + các quyết định người dùng ghi ở phần cập nhật 21–22/10/2026 + các quyết định trong `docs/OPEN_TECHNICAL_DECISIONS.md`. Nếu mâu thuẫn, không tự chọn: ghi decision, cập nhật hợp đồng và xin nhóm/chuyên gia xác nhận.

**Ranh giới sản phẩm:** người dùng xác nhận NeuroPulse là một sản phẩm đồng hành với vòng đeo tay, dự kiến tiếp tục phát triển tới phát hành; giai đoạn hiện tại là nghiên cứu, thử nghiệm physical MVP và demo, không phải nhánh demo dùng một lần. Hiện app vẫn local-first trên Windows 10/11, hỗ trợ mô phỏng và so sánh Piezo/ADXL345. NPI/ngưỡng là giả thuyết thử nghiệm, không phải chẩn đoán hay xác suất mắc Parkinson. “Đầu ngành”, “chính xác”, “sẵn sàng kiểm nghiệm lâm sàng” không thể được xác nhận bằng code/UI đơn thuần; cần dữ liệu, quy trình nghiên cứu, giám sát chuyên môn, xác minh thiết bị và phê duyệt phù hợp. Không quảng bá app là clinical-ready/commercial-ready cho đến khi có bằng chứng và quy trình tương ứng. Thị trường đầu tiên, intended use/claim và chủ sở hữu phê duyệt còn mở ở D-027.

## 1. Trạng thái đã có theo bằng chứng hiện trong repo

Các mục dưới đây có mã/tài liệu hoặc ghi nhận build/test trước đây; chúng **không mặc nhiên được coi là vừa được kiểm tra lại trong lần tạo kế hoạch này**.

- Desktop Electron + React/Vite, API FastAPI local, SQLite metadata và file phiên đo; app mặc định vào Patient mode. Streamlit vẫn còn như đường chẩn đoán/legacy.
- Patient self-measurement workspace, tạo/tra cứu mã bệnh nhân, bắt đầu/dừng đo, waveform live, kết quả/thông báo thử nghiệm và lịch sử theo mã. Nhân viên có các mode Admin/Operator/Researcher/Clinical Reviewer/Kiosk; đây là mode giao diện, không phải xác thực.
- Hai adapter cảm biến, protocol nhị phân CRC, simulator Healthy/Volatile, provenance cho dữ liệu mô phỏng, xử lý Butterworth/Welch, quality gates và công thức NPI thử nghiệm.
- Trang nghiên cứu gồm phiên, hồ sơ, thiết bị/phân tích/algorithm lab và analytics cohort; có SQLite migrations, backup/restore helper, retention service, audit events và export phiên ở backend.
- Ghi nhận kiểm tra lại ngày 2026-10-22: backend `51 passed` (1 cảnh báo deprecation TestClient/Starlette), frontend `2 passed`, desktop build 141 modules và copy thành công sang `desktop/ui`; launcher `-PrepareOnly` qua. Electron launch qua lệnh desktop đã ghi nhận API health thành công và `Main window is ready to show`; Chromium vẫn in cảnh báo cache Access Denied nhưng không chặn cửa sổ. Chưa có visual QA/e2e thao tác đủ flow, cách ly hai mã end-to-end, thiết bị thật/HIL. Không suy diễn các kiểm tra này thành clinical/commercial readiness.

## 2. Backlog theo mức ưu tiên

Trạng thái ban đầu: **CẦN XÁC MINH** nghĩa là có phần triển khai nhưng thiếu bằng chứng end-to-end/độ bao phủ; **THIẾU/CHƯA ĐẠT** nghĩa là handoff/spec ghi rõ còn thiếu hoặc gate chưa qua. Agent tiếp theo phải cập nhật trạng thái kèm bằng chứng, không chỉ tick checkbox.

### P0 — Đóng luồng đo cốt lõi, tính toàn vẹn và độ tin cậy

1. **Luồng bệnh nhân đầu-cuối — CẦN XÁC MINH**
   - **ĐÃ TRIỂN KHAI, ĐÃ KIỂM TRA BACKEND/BUILD; DESKTOP/HIL CẦN XÁC MINH:** NPI live đọc cửa sổ rolling 8 giây từ buffer RAM và cập nhật trong lúc đo; trước đủ thời lượng/quality gate không trả NPI. Patient UI có waveform cuộn, trạng thái chất lượng và countdown 30 giây; backend tự dừng/chốt phiên khi đạt 30 giây, kể cả UI đóng. Backend suite 51 passed, frontend 2 passed, desktop React/Vite build 141 modules và đã copy sang `desktop/ui`. Còn kiểm tra trực quan độ mượt trên Electron và thực tế với cả hai simulator profile.
   - **ĐÃ CÓ CODE; TEST SUITE VÀ BUILD ĐẠT, DESKTOP FLOW CHƯA XÁC MINH:** Patient mode mặc định, tạo hồ sơ/mã và tra cứu theo mã; form submit tên, ngày sinh tùy chọn, XX/XY, tiền sử cá nhân/gia đình tùy chọn và chế độ ăn tùy chọn. Còn thiếu luồng sửa hồ sơ; cần kiểm tra validation, xử lý lỗi và hiển thị thông tin hồ sơ cho bệnh nhân.
   - Còn xác minh đầu-cuối trên Electron: bắt đầu/dừng, waveform từ buffer acquisition, trạng thái kết nối/lỗi, cảnh báo demo gắn phiên bản/quy tắc, lưu đúng mã và tải lịch sử sau restart. Live rolling NPI và tự dừng 30 giây đã có test backend; chưa có bằng chứng desktop/HIL cho hành vi tương ứng.
   - Mã không đổi trong phiên đang đo. Chạy kiểm tra cách ly tối thiểu hai hồ sơ: live buffer, analysis, history và export của mã A không được lộ sang mã B.
   - **ĐÃ CÓ CODE; BACKEND 45 TESTS, FRONTEND 2 TESTS VÀ BUILD ĐẠT; DESKTOP FLOW CHƯA XÁC MINH:** Patient workspace có nút xuất JSON hồ sơ cá nhân và tóm tắt phiên liên kết; payload dành cho bệnh nhân bỏ raw sensor arrays và chi tiết thiết bị/xử lý. API yêu cầu loopback, Patient mode, mã chọn khớp, và ghi audit. Test xác nhận role denial, selected-code isolation và redaction; còn phải kiểm tra trên desktop, empty-history và kết quả thiếu. Patient code không xác thực danh tính.
   - Tiêu chí hoàn tất: workflow chạy được trên desktop, dữ liệu tồn tại sau restart, mọi kết quả truy được về phiên/raw/provenance, test API/UI cho happy path và lỗi.

2. **Thu nhận live và quản lý lỗi — CẦN XÁC MINH**
   - Đảm bảo acquisition chạy trong worker độc lập UI; UI không làm chậm nhận mẫu; buffer có giới hạn/backpressure; mất kết nối, packet lỗi, sequence gap, CRC lỗi, timeout, dừng đột ngột và khởi động lại được thể hiện rõ và không làm hỏng dữ liệu đã lưu.
   - Cơ chế hiện tại là polling định kỳ cho live waveform và rolling NPI; xác minh nhịp cập nhật, độ mượt và tải trên Electron. Không dựa vào hình sóng hardcode. Phân biệt raw preview với phân tích đủ cửa sổ 8s; không nội suy/thay raw để lấp khoảng trống.
   - Ghi measured sample rate, timestamps, sample count, packet loss/jitter và quality flags; không hiển thị target rate như giá trị đo thực tế.
   - Tiêu chí hoàn tất: test tất cả trạng thái và lỗi bằng simulator; UI hiển thị dữ liệu đang đến và cuối phiên đúng với file persisted.

3. **Blocker throughput Piezo — THIẾU/CHƯA ĐẠT, D-006**
   - Frame hiện tại 22 bytes/mẫu × 1000 Hz ≈ 22 kB/s; 115200 baud 8N1 tối đa lý thuyết ≈11.52 kB/s. Chọn giải pháp do hardware team quyết định: batch/timestamp reconstruction hoặc baud rate được firmware/host hỗ trợ.
   - Chốt packet/schema/version, timestamp reconstruction, buffering/CRC/recovery; cập nhật firmware, parser, protocol docs và fixtures đồng bộ. Sau đó HIL đo sustained throughput, sample loss, jitter, rate và recover sau disconnect.
   - Không khẳng định Piezo đạt 1000 Hz trước khi HIL đạt tiêu chí đã thống nhất. Không tự quyết baud/batch thay nhóm.

4. **Firmware và HIL hai cấu hình — THIẾU/CHƯA ĐẠT**
   - Build firmware tái lập bằng toolchain đã chốt; ghi board/firmware/protocol version; kiểm tra handshake, chọn cảm biến, trạng thái cảm biến, lỗi ADC/I2C, reset và reconnect.
   - Piezo: xác nhận board/AFE/gain/bias/ADC attenuation, clipping, calibration raw counts→đơn vị nếu dùng. ADXL345: xác nhận ODR/range/axis/scale/g, raw counts và đơn vị. Không gán cùng ý nghĩa/thang đo cho hai cảm biến.
   - HIL riêng cho từng sensor: đúng kênh/trục, thời gian, độ ổn định dài, dropout, nhiễu, clipping, tháo/rút thiết bị; lưu cấu hình và bằng chứng.
   - D-001…D-006, D-008, D-012 cần được đóng hoặc giữ provisional có owner/điều kiện; thông số chưa xác nhận không được hard-code như sự thật.

5. **Tính đúng của pipeline khoa học — CẦN XÁC MINH / MỘT SỐ QUYẾT ĐỊNH MỞ**
   - Thêm/đối chiếu deterministic ground-truth test: sine/multitone/noise, PSD/Welch scaling, tích phân dải, TBR/NPI, cutoff/biên Nyquist, mẫu ngắn, NaN/Inf, flatline, clipping, saturation, mất mẫu, sample rate sai và từng kênh ADXL345.
   - Giải quyết D-008 (1–20 Hz vs 5–20 Hz và mẫu số TBR), D-010 (ý nghĩa/ngưỡng 0.40/0.85), D-011 (Welch window/overlap/scaling) và profile cho từng sensor. Công thức đã được duyệt **cho thử nghiệm**; không đồng nghĩa tham số/biomarker được xác nhận lâm sàng.
   - Lưu đầy đủ processing profile ID/version, config snapshot, software version/commit, raw hash, channel, units, rate và kết quả từng run. Hiện kết quả một phần nằm trên Session; cần đánh giá run/feature lineage để có thể chạy nhiều thuật toán trên cùng raw mà không ghi đè raw/kết quả cũ.
   - Xác định rõ so sánh Piezo ↔ ADXL345 không trực tiếp tương đương nếu chưa có calibration/normalization protocol.
   - Tiêu chí hoàn tất: test số học với tolerance định trước, kết quả tái lập, raw byte/hash bất biến qua reprocess và export.

6. **Raw data immutability, schema và migrations — CẦN XÁC MINH**
   - Kiểm tra raw HDF5/JSON được tạo độc quyền, checksum xác minh, không ghi đè; metadata đủ provenance (`simulated`, `device`, `imported_benchmark`, `reprocessed`) và simulator scenario/config. Raw không bị xử lý tại chỗ.
   - Migration hiện có; cần kiểm chứng upgrade từ các database thực tế/legacy, backup trước migration, lỗi giữa chừng, downgrade/rollback an toàn và không mất hồ sơ/phiên. Không dùng `create_all` như cơ chế nâng cấp.
   - Xem xét tách rõ participant/study/session/raw recording/processing run/feature set/algorithm version/run/consent/audit theo data contract. Không cần áp dụng schema mục tiêu nếu chưa có migration/data rationale; nhưng phải lưu đủ để truy nguyên và phân tích nhóm.
   - Tiêu chí hoàn tất: migration fixture từ từng schema được hỗ trợ, hash/manifest đối chiếu, backup/restore byte-for-byte, kiểm tra path traversal và file trùng.

7. **Retention, export/delete và backup — THIẾU/CHƯA ĐẠT MỘT PHẦN**
   - Xác minh purge 21 ngày cho hồ sơ, sessions, raw file, exports/cache và liên kết phụ; hành vi active session; giữ vô thời hạn khi được bật; restart/giờ hệ thống sai; audit/consent cần được giữ hay xóa. Có preview/summary trước thao tác phá hủy và audit rõ ràng.
   - Quyết định nhóm đã quy định Admin/Operator/Researcher/Clinical Reviewer được export/delete dữ liệu theo phạm vi prototype; API xóa phiên và export phiên hiện đã cho cả bốn mode. Clinical Reviewer chỉ nhận metadata phiên lâm sàng và không nhận sensor/profile ID, sample rate/count, raw path, checksum, notes hoặc raw channel export. Reviewer cũng bị từ chối cổng serial, trạng thái/luồng acquisition, processing profiles và raw WebSocket; study summary được lọc sensor/cutoff. Toàn bộ 46 backend tests pass; còn phải rà soát khi thêm endpoint mới và xác minh UI trên desktop. Patient vẫn chỉ export hồ sơ/mốc đo theo mã đang chọn. Mode không phải ranh giới bảo mật.
   - Backup utility hiện có và có checksum nhưng archive chưa mã hóa. Chốt chính sách vị trí, quyền truy cập Windows, mã hóa-at-rest/backup, retention backup, restore drill, dung lượng và xử lý khi hỏng ổ đĩa.
   - Tiêu chí hoàn tất: test đủ retention boundary, active recordings, indefinite flag, restore, checksum corruption, overwrite/path traversal và xác nhận không rò dữ liệu giữa patient exports.

8. **Desktop khởi chạy và lỗi vận hành — THIẾU/CHƯA ĐẠT**
   - **ĐÃ CÓ BOOTSTRAP CHO CHECKOUT HIỆN TẠI:** `scripts/start.ps1` kiểm tra Node 20+, frontend/Electron dependencies, Python 3.11+, tạo `.venv` và cài API runtime nếu thiếu; build UI khi Electron chạy. `-PrepareOnly` đã chạy thành công trong workspace. Người dùng trước đây gặp thiếu Electron runtime/Python dependencies; cần kiểm tra shortcut thật, lỗi cài mạng, và khả năng mở lại sau cài.
   - Kiểm tra Electron↔FastAPI lifecycle: port conflict, backend startup/readiness, crash, exit, stale process, app close, local origin/CORS, cache/log location, offline startup.
   - Phân biệt bootstrap cho repository với installer độc lập. Vẫn cần làm installer/runtime bundle, clean install/upgrade/uninstall trên máy Windows 10/11 sạch; data path nằm ngoài thư mục chương trình và được giữ qua update. Lần chuẩn bị đầu tiên hiện cần internet; chưa có offline installer.
   - Tiêu chí hoàn tất: cài/mở/đo mô phỏng/đóng/mở lại trên máy sạch không cần mạng; không có terminal window lỗi; shortcut hợp lệ.

### P1 — Hoàn thiện công cụ nghiên cứu và khả năng dùng hàng ngày

9. **Staff workspaces, mode/action matrix và API — THIẾU/CHƯA ĐẠT MỘT PHẦN**
   - Hoàn thiện matrix Admin/Operator/Researcher/Clinical Reviewer/Kiosk/Patient theo yêu cầu: Operator có quyền xem như Researcher; Clinical Reviewer xem nghiên cứu nhưng ẩn technical codes/raw protocol; Patient không thấy toàn cục/lab/technical; Kiosk hiện là hướng dẫn/chưa có workflow hoàn chỉnh.
   - Thống nhất UI với API. Mode là hạn chế thao tác prototype, không phải đăng nhập/an toàn. Không tuyên bố bảo vệ dữ liệu trước người dùng Windows khác. Trước shared/hospital/consumer deployment phải thiết kế identity/auth/authorization thực sự.
   - Staff cần quyền được yêu cầu: tìm/lọc hồ sơ và phiên, xem dữ liệu phù hợp với mode, quản lý protocol/study, xử lý export/delete theo mode. Session-level export/delete parity hiện có ở API; reviewer bị giới hạn thông tin kỹ thuật tại session list/detail/export và bị chặn các API thiết bị/raw-stream đã rà soát. Còn thiếu bulk export/delete workflow và review rò rỉ kỹ thuật qua các endpoint nghiên cứu còn lại.

10. **Research protocol/study lifecycle — THIẾU/CHƯA ĐẠT MỘT PHẦN**
    - Study CRUD/template đã có nền tảng; hoàn thiện protocol version, inclusion/exclusion, thời lượng, sensor/profile, mã nghiên cứu, operator/session notes, consent reference/state, phiên bản biểu mẫu/quy trình và gắn study-participant-session.
    - Consent UI/log có thể hỗ trợ ghi nhận phiên bản/timestamp, nhưng không thay thế quy trình đồng thuận hoặc phê duyệt đạo đức. Không thu người thật cho đến khi nhóm có cố vấn, protocol, consent và phê duyệt phù hợp.
    - Tiêu chí hoàn tất: nghiên cứu viên tạo protocol, tạo participant/session, truy nguyên phiên về protocol; dữ liệu export giữ protocol version và consent metadata đã được phép.

11. **Analytics/cohort và báo cáo — CẦN XÁC MINH**
    - API/UI lọc provenance, study, ngày UTC bắt đầu/kết thúc, sensor type và quality status. Lọc được áp dụng đồng nhất lên counts, cỡ mẫu và trung bình; ngày cuối tính trọn ngày UTC. Có options lấy từ study/session rows trong SQLite. Backend suite **53 passed** với test lọc kết hợp và biên ngày; frontend **4 passed**.
    - Còn bổ sung lọc profile/session status, missingness và audit cách tính trung bình/không trộn modalities; thêm export báo cáo đọc được. Kiểm tra trực quan/trải nghiệm trên Electron vẫn cần.
    - Thêm biểu đồ mô tả trực quan: số hồ sơ/phiên theo thời gian, phân bố nhóm và so sánh có phân tầng; nêu n, nguồn, trạng thái dữ liệu và loại provenance. Không suy luận ý nghĩa lâm sàng hoặc so sánh nhóm nhỏ như kết luận.
    - Báo cáo/export nghiên cứu tổng thể (CSV/JSON và báo cáo đọc được) cần schema/version, units, quality flags, processing/algorithm snapshots, patient pseudonym; mặc định bỏ PII không cần thiết.
    - Tiêu chí hoàn tất: thống kê tái tạo từ database, khớp dữ liệu fixture đã biết và không đưa simulator vào nhóm dữ liệu người thật.

12. **Algorithm Lab và tái phân tích — THIẾU/CHƯA ĐẠT MỘT PHẦN**
    - Hiện registry/formula compute có, nhưng persisted processing/algorithm run snapshots chưa đầy đủ. Cho phép chạy phiên bản thuật toán/profile khác trên cùng raw bất biến, xem side-by-side kết quả, so sánh có provenance, lưu tham số, và tái lập kết quả.
    - Cảnh báo NPI band 40/70 phải hiển thị tên/rule version, đơn vị, điều kiện không đủ dữ liệu và disclaimer. “Volatile” chỉ là kịch bản tín hiệu tổng hợp có năng lượng dải cao; tuyệt đối không gán nhãn bệnh/nguy cơ cho người.
    - Chưa có dữ liệu nghiên cứu đủ để hiệu chuẩn/đánh giá sensitivity, specificity, ROC/AUC, cutoffs hay xác nhận clinical validity. Chỉ triển khai phân tích thống kê khi có protocol/dataset/owner được phê duyệt.

13. **Simulator/benchmark/test data — CẦN XÁC MINH**
    - Hai scenario Healthy/Volatile đã có ở mức demo provisional; cần xác nhận waveform/parameter/config, deterministic seed, sensor profiles, expected ground truth và lưu provenance đầy đủ.
    - Benchmark import cần schema, units, consent/license/source metadata, validation chống dữ liệu sai/NaN, báo lỗi dòng cụ thể, kiểm tra trùng và provenance riêng.
    - Mọi bảng/chart/export phải phân biệt mô phỏng, benchmark nhập và thiết bị thật. Không dùng synthetic demo làm chứng cứ hiệu năng người bệnh.

14. **UX bệnh nhân, accessibility và an toàn nội dung — CẦN XÁC MINH**
    - Cấu trúc bố cục theo ảnh chú thích đã được cập nhật trong PatientMeasurementPage: waveform chính giữa, NPI trong panel xanh đậm, thông tin phiên ở panel sáng, mã bệnh nhân được nhấn màu đỏ và nút start/stop nằm ở vùng thao tác đầu trang. Desktop UI bundle đã build thành công; chưa mở Electron để kiểm tra hình ảnh thực tế.
    - Còn cần xác minh waveform là nội dung chủ đạo khi đo; NPI thử nghiệm nổi bật nhưng không tạo cảm giác chẩn đoán; status/no-data/error rõ; thông tin đo cá nhân và history dễ đọc; nút start/stop an toàn, có xác nhận khi thao tác có thể mất dữ liệu.
    - UI tiếng Việt thống nhất, font/độ tương phản/kích thước chữ, keyboard, scaling màn hình Windows, hiển thị cho người cao tuổi/thị lực hạn chế, không phụ thuộc màu đơn lẻ để truyền đạt cảnh báo.
    - Thiết kế copy cảnh báo trung tính; không đưa lời khuyên điều trị hay xác suất bệnh. Clinical Reviewer không nhận các mã định danh thiết bị/profile, thông số thu nhận hoặc raw protocol trong luồng phiên; cần rà soát tất cả endpoint khác để bảo đảm cùng nguyên tắc.
    - Patient data entry: ngày tháng, tuổi band, chromosome encoding X=XX/Y=XY, lịch sử, ăn chay/mặn. Không suy đoán giá trị thiếu. Cần xử lý “không rõ/khác” theo quyết định D-023 trước khi mở rộng form.
    - Tiêu chí hoàn tất: review trực quan ở kích thước cửa sổ mục tiêu, keyboard/contrast check, thao tác với người dùng đại diện có giám sát; sửa các lỗi usability nghiêm trọng.

15. **Performance, reliability và observability local — THIẾU/CHƯA ĐẠT**
    - Stress/soak test simulator ở tốc độ và thời lượng dự kiến, bounded memory, render decimation chỉ cho UI, không giảm raw archival; đo CPU/RAM/disk, thời gian mở chart/history, đóng app khi recording, disk full và DB locked.
    - Log file local có rotation/retention, không ghi PII/raw signal vào log không cần thiết; error IDs và support bundle được người dùng tạo chủ động; không telemetry/cloud.
    - Tiêu chí hoàn tất: ngưỡng máy tối thiểu và thời lượng đo được nhóm xác nhận; test soak + restart/recovery pass trên Windows mục tiêu.

### P2 — Nền tảng triển khai có kiểm soát và hướng tới thương mại/nghiên cứu lâm sàng

16. **Security và quyền riêng tư cho triển khai thực — CHƯA ĐẠT**
    - Prototype bỏ sign-in theo yêu cầu và dùng mode + patient code. Patient code là lookup key, không xác thực hay ẩn danh. Trên máy dùng chung, bất kỳ người có quyền Windows phù hợp có thể đọc dữ liệu local.
    - Trước khi chạy trên thiết bị bệnh viện, đa người dùng, phát hành consumer hay lưu dữ liệu nhạy cảm thật: threat model, identity/auth, server-side role authorization, session expiry/recovery, encryption at rest/backup, access audit chống sửa đổi, Windows ACL, secrets, secure update/signing, vulnerability review và incident handling.
    - Quy định data minimization, retention/deletion, consent, export, quyền truy cập, breach response, backup key và dữ liệu nhận dạng. Không mở mạng/API ngoài loopback nếu chưa có kiến trúc bảo mật được review.

17. **Cài đặt/phát hành và quản trị thay đổi — THIẾU/CHƯA ĐẠT**
    - Reproducible build/lockfile/SBOM, dependency/license audit, ký ứng dụng/installer, versioning, release notes, checksum, offline install/upgrade/rollback, kiểm tra tương thích dữ liệu cũ và bảo toàn user data.
    - Tách gói runtime khỏi repo dev để không phát tán `.venv`, `node_modules`, `.git`, cache/test files. Không đóng gói data/session cá nhân trong installer.
    - Quy trình phát hành có release evidence và known limitations; không tự cập nhật qua mạng khi chưa duyệt.

18. **Bằng chứng lâm sàng/hiệu năng và quản trị nghiên cứu — NGOÀI PHẠM VI CODE ĐƠN THUẦN, CHƯA CÓ**
    - Cần cố vấn chuyên môn phù hợp, protocol nghiên cứu được phê duyệt, tiêu chí inclusion/exclusion, consent/assent và quy trình riêng cho trẻ em/người dễ tổn thương, an toàn thiết bị, quản lý adverse event, privacy/ethics/legal approvals theo nơi triển khai.
    - Cần nghiên cứu repeatability/reproducibility, calibration, test-retest, đối chiếu thiết bị/phương pháp tham chiếu, phân tích bias theo tuổi/giới/nhóm, cỡ mẫu được chuyên gia định trước, validation độc lập và statistical analysis plan.
    - Chưa có dữ liệu thật/evidence trong repo để claim diagnostic/screening accuracy, sensitivity/specificity, predictive performance hay clinical cutoff. Thử nghiệm kỹ thuật với simulator không thay thế clinical validation.
    - Nếu muốn thương mại hóa hoặc tuyên bố thiết bị y tế: xác định intended use, phân loại pháp lý và chuẩn áp dụng với chuyên gia/regulatory counsel; quality management/risk management/usability/cybersecurity/clinical evidence, hậu mãi và trách nhiệm sản phẩm. Master spec hiện không hoàn tất các nghĩa vụ này.

## 3. Quyết định chưa chốt cần giữ trong Open Technical Decisions

Agent cần rà soát và cập nhật `docs/OPEN_TECHNICAL_DECISIONS.md`, không tự bịa giá trị:

- D-001..006: board/framework/calibration/sample timing/ODR/serial throughput (D-006 do hardware team quyết định).
- D-008..013: profile/filter/TBR denominator/Welch/NPI thresholds/ADXL multi-axis/storage format. D-009 formula được duyệt ở mức thử nghiệm; ngưỡng không có xác nhận lâm sàng.
- D-019: encryption/backup retention/audit tamper evidence/threat model.
- D-020: patient code dùng năm tạo hồ sơ hay lần đo đầu tiên, century handling và uniqueness scope.
- D-023: chromosome marker không rõ/khác XX/XY và quan hệ với thông tin giới tính/tuổi; không suy luận sinh học từ trường mã.
- D-024: Electron/Python runtime đóng gói, installer, data path, upgrade/uninstall.
- D-025: simulator parameter và cohort metric review bởi nhóm nghiên cứu.
- D-026: xác minh Patient self-measurement, cách ly hai mã và profile Piezo/ADXL trên desktop.
- Xung đột tài liệu: README/handoff cũ có hướng dẫn Streamlit/login/role/default mode không còn đúng; cập nhật có kiểm soát, giữ lịch sử thay vì để agent làm theo hướng dẫn stale.

## 4. Thứ tự triển khai đề xuất và cổng nghiệm thu

1. **M0 — Baseline & repo truth:** xác nhận trạng thái git/dependencies, đọc toàn bộ spec, cập nhật gap ledger; tái lập build/test trong môi trường được ghi nhận. Không đánh dấu mục cũ complete nếu chưa tái xác minh.
2. **M1–M3 — Protocol, firmware, acquisition:** đóng contract/throughput với hardware team; simulator failures; HIL hai sensor. Không qua gate nếu timing/loss chưa đo.
3. **M4–M5 — Processing/algorithms:** ground-truth test, chốt profile/decision, persist immutable run snapshots và quality failures.
4. **M6 — Data/privacy:** migration, patient data isolation, retention, export/delete, backup/restore/audit; test full lifecycle.
5. **M7–M8 — Desktop/workflows:** Patient self-measurement end-to-end, staff modes/analytics/research protocol, accessibility/usability, role-data matrix.
6. **M9 — Integration readiness:** deterministic API/UI integration/e2e, soak/recovery, cross-profile and two-patient tests; sửa tài liệu/handoff.
7. **M10 — HIL:** chạy protocol thử nghiệm phần cứng trên hai cấu hình, lưu raw và evidence; không gộp dữ liệu simulated với device.
8. **M11 — Internal MVP release:** installer/offline clean-machine, backup/restore, support docs, known limits, release report. Đây chỉ là internal research MVP gate, chưa xác nhận clinical/commercial readiness.
9. **Clinical/commercial gate:** chỉ sau các hoạt động chuyên môn/đạo đức/pháp lý và validation nêu trên; agent code không thể tự đóng gate thay tổ chức/cố vấn.

## 5. Quy tắc hoàn thành cho agent tiếp theo

- Tiến theo milestone, không nhảy thẳng sang feature demo. Mỗi thay đổi interface phải cập nhật data contract/API/docs và test tương ứng.
- Thực hiện test deterministic/integration phù hợp với task và ghi chính xác command/kết quả; nếu không chạy được, nêu nguyên nhân và không nhận là pass.
- Mỗi checkbox cần trạng thái `TODO / IN PROGRESS / BLOCKED BY DECISION / VERIFIED` và link đến file/test/log/bằng chứng. HIL/clinical evidence phải chỉ rõ thiết bị, cấu hình, ngày, operator và protocol; không bịa.
- Không xóa hoặc làm sạch dữ liệu phiên, database, backup hay thư mục chưa phân loại chỉ nhằm giảm số file.
- Bảo toàn raw data, provenance, checksum và safety disclaimers; không dùng hardcode/mock như dữ liệu thật.
- Cập nhật `HANDOFF.md`, `drift-away.md` và open decisions khi trạng thái/kiến trúc thay đổi; ghi rõ những mục còn phụ thuộc hardware team, clinical advisor, ethics/regulatory owner.

## 6. Mục tiêu “hoàn chỉnh” phải được gọi đúng tên

- **Demo prototype:** mô phỏng, UI và workflow local hoạt động; dữ liệu mô phỏng luôn gắn nhãn.
- **Internal research MVP:** cài được trên máy sạch, đo phần cứng đã xác minh, dữ liệu truy nguyên/toàn vẹn, protocol/consent/retention/backup và test gates đạt.
- **Clinical-study-ready:** ngoài software gates còn phải có phê duyệt/protocol/consent/giám sát chuyên môn/thiết bị an toàn và validation phù hợp.
- **Commercial/medical-ready:** cần thêm intended use, regulatory pathway, quality/risk/cybersecurity/usability/clinical evidence và vận hành được thẩm định. Đây không phải cam kết của MVP spec và không thể suy ra từ phần trăm code hoàn thành.

**Kết luận trạng thái tại thời điểm lập kế hoạch:** repo có nền tảng full-stack local và simulator/processing/UI đáng kể, nhưng các gate cốt lõi còn mở gồm xác minh desktop đầu-cuối, cách ly Patient, Patient export, role/API parity, audit/provenance đầy đủ, retention/backup policy, installer clean-machine, D-006 và HIL hai sensor. Chưa có bằng chứng clinical validation; app chưa được gọi là sẵn sàng thử nghiệm lâm sàng hoặc commercial-ready.

## Follow-up items added 2026-10-22
- [x] Replace chromosome selection with reported-sex selection and explicit internal mapping; retain legacy compatibility.
- [x] Collapse patient profile creation behind a clear action; expose patient history navigation.
- [x] Add detailed technical algorithm documentation and persistent formula version/retirement workflow for baseline parameters.
- [ ] Bind algorithm/profile version and parameter snapshot to each session and reanalysis before enabling alternative formulas in acquisition.
- [x] Add a bounded arithmetic DSL with runtime validation and tests for custom Lab formulas; arbitrary code execution is rejected. [ ] Define expert review/approval workflow and expanded validation evidence before research use.
- [ ] Extend participant data dictionary to unknown/not-disclosed/other categories before recruitment outside prototype scope.
- [ ] Complete desktop click-through, simulator and hardware-in-loop verification; no physical-device or clinical validation evidence exists yet.
- [ ] Apply research reporting gates from docs/RESEARCH_QUALITY_PLAN.md before any clinical-accuracy study claims.

## Follow-up items added 2026-10-22 — research reproducibility
- [x] Re-run stored completed raw sessions from Algorithm Lab using a selected safe-DSL formula; include sensor/channel/provenance/rate/quality and version/parameter lineage in response and audit.
- [x] Add a dedicated persistent algorithm_evaluations table, local history API, and Lab history display alongside audit events. Research export/statistics inclusion remains open.
- [ ] Verify session formula reanalysis through an interactive desktop click-through with both Piezo and ADXL345 data; current automated session test mocks the reprocessing pipeline.
- [ ] Resolve full backend test-suite hang in local Windows environment; focused suites pass but the whole suite was not confirmed this turn.
- [ ] Determine why the desktop process returned exit code -2147483645 after renderer load; current logs show DOM ready/did-finish-load but no visual confirmation.

## Follow-up items added 2026-10-22 — persistent formula evaluations
- [x] Persist Algorithm Lab evaluations in `algorithm_evaluations`, with a paginated API and staff history view; keep audit entries as an additional action record.
- [x] Add a staff CSV/JSON export endpoint for formula evaluations. [ ] Include evaluation records in cohort statistics and comprehensive research packages.
- [ ] Verify actual desktop reanalysis using saved Piezo and ADXL345 sessions; current automated route test mocks the processing call.
- [ ] Confirm retention/deletion behavior for formula evaluation rows when associated patient/session records expire or are deleted.
- [ ] Complete deterministic test suite in the Windows local environment; the full-suite run previously stalled while focused tests passed.

## Follow-up — Algorithm evaluation export
- [x] Export saved formula evaluation history as staff CSV/JSON and include source metadata and experiment-only labeling.
- [ ] Include this data in comprehensive research exports and cohort statistics; define retention/deletion behavior for orphaned evaluation rows.
- [x] Delete session-linked formula evaluation rows when the source session is deleted or purged by patient-retention expiry.
- [ ] Decide how manual evaluations without a session link are retained or cleared.
- [x] Cascade session-linked formula evaluations with session soft-delete and patient-expiry cleanup; add expiry regression coverage.
- [x] Escape spreadsheet formula-leading text in CSV exports and regression-test it.
- [ ] Resolve intermittent Electron exit code `-2147483645` after fresh launch, capturing current stdout/stderr and Windows crash data; past DOM-ready logs do not establish stable repeat launches.

## UI polish follow-up — 2026-10-22
- [x] Add a persisted dark/light theme switch and persisted collapsible sidebar.
- [x] Apply glass surfaces, ambient gradient and spectrum accents to the Electron/React UI; add reduced-motion styling.
- [x] Rebuild bundled desktop UI and run existing frontend tests (4 passed; 141 Vite modules built).
- [ ] Visually inspect the actual Electron window in both themes and expanded/collapsed layouts; verify readability, focus states, chart labels and compact-window behavior.
- [ ] Refresh the existing Desktop transfer folder only after the source-root implementation and context notes are complete; verify checksums and exclude patient data, raw captures, caches and virtual environments.

## UI defect follow-up — Windows native dropdown (2026-10-22)
- [x] Fix unreadable dark-mode role options by explicitly styling native select options against their popup background.
- [x] Re-run frontend tests (4 passed) and desktop TypeScript/Vite bundle (141 modules).
- [ ] Confirm in an actual Windows Electron screenshot in both themes; replace native select with an accessible custom listbox only if native option styling is ignored.
- [ ] Re-test patient workflow using a valid generated code; the screenshot's entered `O` correctly produced the no-profile state, so that state alone is not evidence of a workflow bug.

## Responsiveness follow-up — 2026-10-22
- [x] Remove repeated card/sidebar backdrop blur and decorative blur layers; reduce large shadows and chart filters.
- [x] Avoid rerendering App/routes/charts on theme and sidebar toggles; update presentation preferences without React root state.
- [x] Remove root background/width transitions; tests 4 passed and desktop bundle 141 modules built.
- [ ] Measure perceived responsiveness and chart FPS in actual Electron with same-size repeated theme toggles and active simulator/device stream; record method and result before claiming FPS improvement.
- [ ] If slow under active capture persists, profile polling cadence, waveform SVG point count and state-update scope separately; do not reduce sampling/storage fidelity to mask UI lag.
