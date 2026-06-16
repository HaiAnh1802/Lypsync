# ===== CHẠY CELL NÀY TRƯỚC BƯỚC 9 =====
# Fix lỗi: No module named 'torchvision.transforms.functional_tensor'

import sys
import torchvision.transforms.functional as F

# Monkey-patch module bị thiếu
sys.modules['torchvision.transforms.functional_tensor'] = F

# Verify fix
try:
    import torchvision.transforms.functional_tensor
    print("✅ Fix thanh cong!")
except:
    print("❌ Van loi, thu cach 2...")
    # Cach 2: Downgrade basicsr
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'basicsr==1.4.2', '-q'])
    print("✅ Da downgrade basicsr==1.4.2, restart kernel va thu lai")
