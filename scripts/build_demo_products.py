from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
products=[]
catalog={
"Thời trang":["Áo Hoodie Basic","Áo Polo Cotton","Áo Khoác Nhẹ","Quần Jeans Straight","Váy Midi Tối Giản","Mũ Bucket","Túi Đeo Chéo","Giày Sneaker Daily"],
"Điện tử":["Tai nghe Bluetooth","Loa Mini Không Dây","Bàn phím Compact","Chuột Không Dây","Sạc nhanh 30W","Đèn bàn LED","Giá đỡ Laptop","Cáp Type-C Bền"],
"Sức khỏe & Làm đẹp":["Sữa rửa mặt dịu nhẹ","Kem dưỡng ẩm","Son tint lì","Kem chống nắng","Serum phục hồi","Nước tẩy trang","Dầu gội thảo mộc","Mặt nạ dưỡng ẩm"],
"Nhà cửa & Đời sống":["Bình giữ nhiệt","Hộp đựng thực phẩm","Đèn ngủ để bàn","Kệ mini đa năng","Khăn tắm cotton","Gối tựa lưng","Bộ cốc thủy tinh","Thảm lau chân"],
"Mẹ & Bé / Đồ chơi":["Bộ xếp hình sáng tạo","Xe đồ chơi mini","Bình nước trẻ em","Bộ tô màu","Thú bông mềm","Bộ thẻ học chữ","Hộp đồ chơi lắp ghép","Balo trẻ em"],
}
idx=1
for ci,(category,names) in enumerate(catalog.items()):
    for ni,name in enumerate(names):
        products.append({
            "id":idx,
            "external_id":f"demo-{idx:04d}",
            "name":name,
            "category":category,
            "price":float(59000 + ((ci*8+ni)*37000)%850000),
            "description":f"Sản phẩm demo thuộc danh mục {category}. Dữ liệu này chỉ phục vụ chạy giao diện offline; script Lazada sẽ thay catalog demo bằng metadata sản phẩm thật.",
            "image_path":None,
            "image_url":None,
            "source":"demo_fixture"
        }); idx+=1
path=ROOT/'data/demo_products.json'
path.write_text(json.dumps(products,ensure_ascii=False,indent=2),encoding='utf-8')
print('wrote',len(products),path)
