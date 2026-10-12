import json
import requests
import os

class AiSolver:
    def __init__(self, api_key):
        self.api_key = api_key
        # Danh sách model thử lần lượt: mỗi model có quota riêng (20 lần/ngày)
        # Nếu model chính bị 503/hết quota, tự chuyển sang model khác
        self.models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.8-flash"]

    def solve(self, raw_assignment_text):
        prompt = f"""
        Bạn là một lập trình viên xuất sắc. Dưới đây là nội dung văn bản quét được từ một trang bài tập lập trình cụ thể.
        Nhiệm vụ của bạn:
        1. Phân tích nội dung và bóc tách YÊU CẦU DUY NHẤT của bài tập này. KHÔNG tự sáng tác thêm đề bài.
        2. Viết mã nguồn hoàn chỉnh hoặc câu trả lời văn bản để giải quyết bài tập đó.
        3. Chọn tên file phù hợp (vd: bai1.java, bai2.js, script.sql...).
        
        Nội dung trang web:
        ---
        {raw_assignment_text}
        ---
        
        Hãy trả về kết quả theo cấu trúc thẻ (XML-like) dưới đây. KHÔNG dùng định dạng JSON vì rất dễ lỗi ngoặc kép:
        
        <FILENAME>tên_file_ở_đây.txt</FILENAME>
        <CODE>
        viết_mã_nguồn_hoặc_câu_trả_lời_ở_đây
        </CODE>
        <EXPLANATION>
        giải_thích_ngắn_gọn_ở_đây
        </EXPLANATION>
        """
        
        import time
        import re
        
        for model in self.models:
            print(f"🧠 Đang gửi đề bài cho AI phân tích và giải ({model} - REST API)...")
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            
            quota_exhausted = False
            
            for attempt in range(6):
                try:
                    response = requests.post(url, headers=headers, json=data, timeout=120)
                    response.raise_for_status()
                    
                    res_json = response.json()
                    content = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    # Bóc tách bằng Regex thay vì parse JSON
                    filename_match = re.search(r'<FILENAME>(.*?)</FILENAME>', content, re.IGNORECASE | re.DOTALL)
                    code_match = re.search(r'<CODE>(.*?)</CODE>', content, re.IGNORECASE | re.DOTALL)
                    
                    if filename_match and code_match:
                        result = [{
                            "filename": filename_match.group(1).strip(),
                            "code": code_match.group(1).strip(),
                            "exercise_name": "BAI"
                        }]
                    else:
                        result = [{
                            "filename": "bai_tap.txt",
                            "code": content,
                            "exercise_name": "BAI"
                        }]
                    
                    print("⏳ Nghỉ ngơi 10s để tránh làm Google quá tải...")
                    time.sleep(10)
                    
                    return result
                except requests.exceptions.Timeout:
                    print(f"⚠️ Cảnh báo: Lần thử {attempt + 1}/6 bị quá thời gian (Timeout). Đang thử lại sau 5s...")
                    time.sleep(5)
                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:
                        # Kiểm tra xem có phải hết quota ngày không (retryDelay > 300s = 5 phút)
                        try:
                            err_json = response.json()
                            details = err_json.get("error", {}).get("details", [])
                            for d in details:
                                if d.get("@type", "").endswith("RetryInfo"):
                                    delay_str = d.get("retryDelay", "0s")
                                    delay_sec = int(''.join(filter(str.isdigit, delay_str.split('.')[0])) or '0')
                                    if delay_sec > 300:
                                        print(f"🛑 HẾT QUOTA NGÀY cho model {model}! Google yêu cầu đợi {delay_sec // 3600}h{(delay_sec % 3600) // 60}m.")
                                        print(f"   ➡️ Chuyển sang model dự phòng...")
                                        quota_exhausted = True
                                        break
                        except:
                            pass
                        
                        if quota_exhausted:
                            break
                        
                        print(f"⏳ Bị giới hạn tốc độ (429). Đợi 60s rồi thử lại...")
                        time.sleep(60)
                    elif response.status_code in [500, 502, 503, 504]:
                        print(f"⚠️ Máy chủ Google quá tải (Lỗi {response.status_code}). Đợi 20s để thử lại ({attempt + 1}/6)...")
                        time.sleep(20)
                    elif response.status_code == 404:
                        print(f"❌ Model {model} không tồn tại (404). Chuyển model khác...")
                        break
                    else:
                        print(f"❌ Lỗi HTTP khi gọi API Google AI: {e}")
                        break
                except requests.exceptions.RequestException as e:
                    print(f"❌ Lỗi mạng khi gọi API Google AI: {e}")
                    break
                except Exception as e:
                    print(f"❌ Lỗi khi bóc tách kết quả từ AI: {e}")
                    print(f"Raw response: {content if 'content' in locals() else 'None'}")
                    break
            
            if quota_exhausted:
                continue  # Thử model tiếp theo
            
            print(f"❌ Thất bại sau 6 lần thử với model {model}.")
            # Nếu 503 liên tục, thử model khác
            print(f"   ➡️ Chuyển sang model dự phòng...")
            continue
        
        print("❌ Tất cả các model đều thất bại.")
        return None
