import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import json
from google import genai
from google.genai import types

# Cấu hình giao diện Streamlit
st.set_page_config(page_title="AI Pre-press Proofreader", layout="wide", page_icon="🖨️")

st.title("🖨️ Công Cụ Rà Soát Lỗi Thiết Kế & Chính Tả Trước In Ấn")
st.caption("Tự động kiểm tra file PDF/Ảnh: chính tả tiếng Việt, dấu Telex/VNI, số điện thoại, lặp hình, rác vector, chất lượng ảnh.")

# Sidebar nhập cấu hình
with st.sidebar:
    st.header("⚙️ Cấu hình")
    api_key = st.text_input("Nhập Google Gemini API Key:", type="password")
    st.info("API Key được tạo miễn phí tại Google AI Studio.")

uploaded_file = st.file_uploader("Kéo thả file thiết kế (PDF, PNG, JPG):", type=["pdf", "png", "jpg", "jpeg"])

def convert_pdf_to_images(pdf_bytes):
    """Chuyển đổi từng trang PDF thành hình ảnh PIL"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    return images

def analyze_image_with_ai(image: Image.Image, client: genai.Client):
    """Gửi ảnh đến Gemini để rà soát lỗi in ấn, chính tả và đồ họa"""
    prompt = """
    Bạn là chuyên gia rà soát bản in ấn và thiết kế đồ họa (Pre-press Proofreader) khắt khe.
    Hãy phân tích toàn bộ bức ảnh thiết kế này và chỉ ra các lỗi:

    1. LỖI VĂN BẢN & NỘI DUNG:
       - Chính tả tiếng Việt, dấu Telex/VNI, gõ nhầm từ.
       - Sai thông tin then chốt: Số điện thoại (thừa/thiếu số), địa chỉ, ngày tháng năm.

    2. LỖI HÌNH ẢNH & ĐỒ HỌA:
       - Lặp hình: Logo, biểu tượng hoặc cụm chi tiết bị nhân đôi/dán đè lặp lại vô lý.
       - Rác vector/chi tiết thừa: Nét vẽ lạc, điểm chấm vô nghĩa, khung viền rỗng còn sót lại.
       - Chất lượng ảnh: Hình ảnh có dấu hiệu mờ, vỡ hạt (pixelated), bệt màu hoặc cắt ghép viền lem nhem, không đạt chuẩn in ấn.
       - Bố cục: Chi tiết quan trọng (chữ, logo) nằm quá sát mép cắt (dễ bị phạm khi xén giấy).

    HÃY TRẢ VỀ DẠNG JSON DUY NHẤT (không dùng markdown codeblock, chỉ chuỗi json thuần):
    {
        "status": "has_errors" hoặc "clean",
        "total_errors": số_lỗi,
        "errors": [
            {
                "original_text": "Tên chi tiết hoặc đoạn chữ bị lỗi",
                "corrected_text": "Đề xuất khắc phục (hoặc 'N/A' nếu là lỗi hình ảnh)",
                "error_type": "Chính tả / Chi tiết thừa / Lặp hình / Chất lượng ảnh / Cắt phạm lề",
                "location_hint": "Vị trí cụ thể trên ấn phẩm",
                "explanation": "Mô tả chi tiết lỗi đồ họa hoặc văn bản phát hiện được"
            }
        ]
    }
    Nếu thiết kế hoàn toàn sạch lỗi, trả về "status": "clean" và "errors": [].
    """
    
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=[image, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return response.text

if uploaded_file and api_key:
    client = genai.Client(api_key=api_key)
    
    # Xử lý file đầu vào thành danh sách ảnh
    if uploaded_file.name.endswith(".pdf"):
        with st.spinner("Đang trích xuất các trang PDF..."):
            pages = convert_pdf_to_images(uploaded_file.read())
    else:
        pages = [Image.open(uploaded_file)]

    st.success(f"Đã tải thành công file với {len(pages)} trang/mặt thiết kế.")

    # Duyệt qua từng trang để kiểm tra
    for idx, page_img in enumerate(pages):
        st.divider()
        st.subheader(f"📄 Kiểm tra Trang {idx + 1}")
        
        col_img, col_res = st.columns([1, 1])
        
        with col_img:
            st.image(page_img, caption=f"Trang {idx + 1}", use_container_width=True)
            
        with col_res:
            check_btn = st.button(f"🔍 Quét lỗi Trang {idx + 1}", key=f"btn_{idx}")
            
            if check_btn:
                with st.spinner("AI đang quét câu chữ và kiểm tra lỗi đồ họa..."):
                    try:
                        raw_result = analyze_image_with_ai(page_img, client)
                        data = json.loads(raw_result)
                        
                        if data.get("status") == "clean" or len(data.get("errors", [])) == 0:
                            st.balloons()
                            st.success("✅ Tuyệt vời! Không phát hiện lỗi chính tả, rác vector hay sai sót đồ họa nào trên trang này.")
                        else:
                            st.warning(f"⚠️ Phát hiện {len(data.get('errors', []))} điểm cần lưu ý:")
                            for err in data.get("errors", []):
                                with st.expander(f"🔴 [{err.get('error_type')}] {err.get('original_text')} ➜ {err.get('corrected_text')}"):
                                    st.write(f"**Vị trí:** {err.get('location_hint')}")
                                    st.write(f"**Lý do:** {err.get('explanation')}")
                    except Exception as e:
                        st.error(f"Đã xảy ra lỗi khi quét: {str(e)}")

elif uploaded_file and not api_key:
    st.warning("Vui lòng nhập API Key ở thanh bên trái để bắt đầu kiểm tra.")