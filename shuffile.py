import os
import shutil
import random

# Đường dẫn thư mục ảnh và nhãn
images_folder = "E:/Data_KHOI/Project_YOLO/dataset/SVHN/SVHN/images"  # Thay bằng đường dẫn thư mục ảnh
labels_folder = "E:/Data_KHOI/Project_YOLO/dataset/SVHN/SVHN/labels"  # Thay bằng đường dẫn thư mục nhãn
output_folder = "E:/Data_KHOI/Project_YOLO/dataset/SVHN"  # Thay bằng đường dẫn thư mục lưu dữ liệu chia

# Tạo các thư mục train, val, test
splits = ["train", "val", "test"]
for split in splits:
    os.makedirs(os.path.join(output_folder, split, "images"), exist_ok=True)
    os.makedirs(os.path.join(output_folder, split, "labels"), exist_ok=True)

# Tỉ lệ chia dữ liệu
train_ratio = 0.8  # Tỉ lệ tập huấn luyện
val_ratio = 0.0    # Tỉ lệ tập xác minh
test_ratio = 0.2    # Tỉ lệ tập kiểm tra

# Lấy danh sách các file ảnh
image_files = [f for f in os.listdir(images_folder) if f.endswith(".jpg") or f.endswith(".png")]

# Đếm tổng số lượng ảnh
total_images = len(image_files)
print(f"Tổng số lượng ảnh: {total_images}")

# Tính số lượng ảnh cho từng tập
num_train = int(total_images * train_ratio)
num_val = int(total_images * val_ratio)
num_test = total_images - num_train - num_val  # Đảm bảo tổng đúng 100%

print(f"Số lượng ảnh mỗi tập:")
print(f" - Train: {num_train}")
print(f" - Validation: {num_val}")
print(f" - Test: {num_test}")

# Trộn ngẫu nhiên danh sách ảnh
random.shuffle(image_files)

# Chia dữ liệu
train_files = image_files[:num_train]
val_files = image_files[num_train:num_train + num_val]
test_files = image_files[num_train + num_val:]

# Hàm di chuyển file
def move_files(file_list, split):
    for image_file in file_list:
        label_file = image_file.replace(".jpg", ".txt").replace(".png", ".txt")
        # Di chuyển ảnh
        shutil.copy(os.path.join(images_folder, image_file), os.path.join(output_folder, split, "images", image_file))
        # Kiểm tra nếu nhãn tồn tại thì mới di chuyển
        label_path = os.path.join(labels_folder, label_file)
        if os.path.exists(label_path):
            shutil.copy(label_path, os.path.join(output_folder, split, "labels", label_file))

# Di chuyển file vào từng thư mục
move_files(train_files, "train")
move_files(val_files, "val")
move_files(test_files, "test")

print("Hoàn thành chia dữ liệu!")