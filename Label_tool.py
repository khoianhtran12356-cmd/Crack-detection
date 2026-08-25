import sys
import os
import math
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPixmap, QPen, QColor, QFont, QPainter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QListWidget, QInputDialog, QLabel, QMessageBox
)

class LabelingCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Trạng thái dữ liệu ảnh & box
        self.image_path = ""
        self.pixmap = None
        self.scale = 1.0
        self.offset = QPointF(0, 0)
        
        # Danh sách box: dict(class_id, x_center, y_center, width, height)
        self.boxes = []
        
        # Danh sách nhãn: dict(id, name)
        self.classes = []
        self.current_class_id = 0

        # Kích thước box nháp (mặc định tối ưu cho ảnh 224 - 640)
        self.draft_width = 80
        self.draft_height = 80

        # Trạng thái tương tác
        self.mode = "suggest" # "suggest" (gợi ý/vẽ) hoặc "select" (chọn/sửa)
        self.alt_pressed = False
        self.ctrl_pressed = False
        self.is_drawing_drag = False
        
        self.selected_box_idx = -1
        self.resizing_handle = None # 'tl' (top-left), 'br' (bottom-right)
        self.drag_start_img_pos = QPointF()

    def set_image(self, image_path, boxes=None):
        self.image_path = image_path
        self.pixmap = QPixmap(image_path)
        self.boxes = boxes if boxes is not None else []
        self.selected_box_idx = -1
        self.scale = 1.0
        self.offset = QPointF(0, 0)
        self.is_drawing_drag = False
        
        # Tự động điều chỉnh độ mở rộng góc nhìn thích hợp cho ảnh 224 - 640
        if self.pixmap and not self.pixmap.isNull():
            w = self.pixmap.width()
            if w <= 320:
                self.scale = 1.8
            elif w <= 640:
                self.scale = 1.2
        self.update()

    def img_to_canvas(self, point):
        return QPointF(point.x() * self.scale + self.offset.x(),
                       point.y() * self.scale + self.offset.y())

    def canvas_to_img(self, point):
        return QPointF((point.x() - self.offset.x()) / self.scale,
                       (point.y() - self.offset.y()) / self.scale)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Vẽ Ảnh
        if self.pixmap and not self.pixmap.isNull():
            scaled_w = self.pixmap.width() * self.scale
            scaled_h = self.pixmap.height() * self.scale
            target_rect = QRectF(self.offset.x(), self.offset.y(), scaled_w, scaled_h)
            painter.drawPixmap(target_rect, self.pixmap, QRectF(self.pixmap.rect()))
        else:
            return

        img_w, img_h = self.pixmap.width(), self.pixmap.height()

        # 2. Vẽ các Bounding Box đã lưu
        for idx, b in enumerate(self.boxes):
            cx, cy = b['x_center'] * img_w, b['y_center'] * img_h
            bw, bh = b['width'] * img_w, b['height'] * img_h
            
            x1 = (cx - bw/2) * self.scale + self.offset.x()
            y1 = (cy - bh/2) * self.scale + self.offset.y()
            w_c = bw * self.scale
            h_c = bh * self.scale
            
            rect = QRectF(x1, y1, w_c, h_c)
            is_selected = (idx == self.selected_box_idx)
            
            pen = QPen(QColor(255, 0, 0) if is_selected else QColor(0, 255, 0), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Tên Class hiển thị trên Box
            class_name = f"ID:{b['class_id']}"
            for c in self.classes:
                if c['id'] == b['class_id']:
                    class_name = f"[{c['id']}] {c['name']}"
                    break
            
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(int(x1), int(max(12, y1 - 4)), class_name)

            # Vẽ nút kéo góc điều chỉnh kích thước
            if is_selected:
                painter.setBrush(QColor(0, 0, 255))
                painter.drawRect(QRectF(x1 - 4, y1 - 4, 8, 8))       # Top-Left (TL)
                painter.drawRect(QRectF(x1 + w_c - 4, y1 + h_c - 4, 8, 8)) # Bottom-Right (BR)

        # 3. Vẽ Box gợi ý nháp hoặc khung chọn kéo thả
        if self.mode == "suggest" and self.underMouse():
            cursor_pos = self.mapFromGlobal(self.cursor().pos())
            painter.setPen(QPen(QColor(255, 255, 0), 1.5, Qt.DashLine))

            if self.is_drawing_drag:
                # Kéo thả chuột vẽ khung nét đứt
                start_c = self.img_to_canvas(self.drag_start_img_pos)
                rect_drag = QRectF(start_c, cursor_pos).normalized()
                painter.drawRect(rect_drag)
            else:
                # Hiển thị box gợi ý nháp quanh tâm con trỏ chuột
                bw_c = self.draft_width * self.scale
                bh_c = self.draft_height * self.scale
                x1 = cursor_pos.x() - bw_c / 2
                y1 = cursor_pos.y() - bh_c / 2
                
                painter.drawRect(QRectF(x1, y1, bw_c, bh_c))
                painter.setPen(QPen(QColor(255, 255, 0)))
                painter.drawPoint(cursor_pos)

    def mousePressEvent(self, event):
        if not self.pixmap or self.pixmap.isNull():
            return

        pos = event.pos()
        img_pos = self.canvas_to_img(pos)
        img_w, img_h = self.pixmap.width(), self.pixmap.height()

        if event.button() == Qt.LeftButton:
            if self.mode == "suggest":
                self.is_drawing_drag = True
                self.drag_start_img_pos = img_pos
                self.update()
            
            elif self.mode == "select":
                # Kiểm tra kéo góc box đang chọn
                if self.selected_box_idx >= 0:
                    b = self.boxes[self.selected_box_idx]
                    cx, cy = b['x_center'] * img_w, b['y_center'] * img_h
                    bw, bh = b['width'] * img_w, b['height'] * img_h
                    x1, y1 = cx - bw/2, cy - bh/2
                    x2, y2 = cx + bw/2, cy + bh/2

                    threshold = 12 / self.scale
                    dist_tl = math.hypot(img_pos.x() - x1, img_pos.y() - y1)
                    dist_br = math.hypot(img_pos.x() - x2, img_pos.y() - y2)

                    if dist_tl < threshold:
                        self.resizing_handle = 'tl'
                        return
                    elif dist_br < threshold:
                        self.resizing_handle = 'br'
                        return

                # Chọn box khác khi click vào vùng thuộc tính
                self.selected_box_idx = -1
                for idx, b in enumerate(self.boxes):
                    cx, cy = b['x_center'] * img_w, b['y_center'] * img_h
                    bw, bh = b['width'] * img_w, b['height'] * img_h
                    rect = QRectF(cx - bw/2, cy - bh/2, bw, bh)
                    if rect.contains(img_pos):
                        self.selected_box_idx = idx
                        break
                self.update()

    def mouseMoveEvent(self, event):
        if self.mode == "suggest":
            self.update()
            
        elif self.mode == "select" and self.resizing_handle and self.selected_box_idx >= 0:
            img_pos = self.canvas_to_img(event.pos())
            img_w, img_h = self.pixmap.width(), self.pixmap.height()
            
            b = self.boxes[self.selected_box_idx]
            cx, cy = b['x_center'] * img_w, b['y_center'] * img_h
            bw, bh = b['width'] * img_w, b['height'] * img_h
            x1, y1 = cx - bw/2, cy - bh/2
            x2, y2 = cx + bw/2, cy + bh/2

            if self.resizing_handle == 'tl':
                # Góc trỏ dưới phải (x2, y2) giữ cố định
                x1_new, y1_new = img_pos.x(), img_pos.y()
                new_w = max(4, x2 - x1_new)
                new_h = max(4, y2 - y1_new)
                new_cx = x2 - new_w / 2
                new_cy = y2 - new_h / 2
            else: # 'br'
                # Góc trỏ trên trái (x1, y1) giữ cố định
                x2_new, y2_new = img_pos.x(), img_pos.y()
                new_w = max(4, x2_new - x1)
                new_h = max(4, y2_new - y1)
                new_cx = x1 + new_w / 2
                new_cy = y1 + new_h / 2

            b['x_center'] = new_cx / img_w
            b['y_center'] = new_cy / img_h
            b['width'] = new_w / img_w
            b['height'] = new_h / img_h
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.mode == "suggest" and self.is_drawing_drag:
            self.is_drawing_drag = False
            img_pos = self.canvas_to_img(event.pos())
            img_w, img_h = self.pixmap.width(), self.pixmap.height()

            x1 = min(self.drag_start_img_pos.x(), img_pos.x())
            y1 = min(self.drag_start_img_pos.y(), img_pos.y())
            x2 = max(self.drag_start_img_pos.x(), img_pos.x())
            y2 = max(self.drag_start_img_pos.y(), img_pos.y())

            w = x2 - x1
            h = y2 - y1

            # Click nhanh nhẹ -> Dùng độ rộng/cao gợi ý nháp
            if w < 5 or h < 5:
                w = self.draft_width
                h = self.draft_height
                cx = img_pos.x()
                cy = img_pos.y()
            else:
                cx = x1 + w / 2
                cy = y1 + h / 2

            new_box = {
                'class_id': self.current_class_id,
                'x_center': cx / img_w,
                'y_center': cy / img_h,
                'width': w / img_w,
                'height': h / img_h
            }
            self.boxes.append(new_box)
            self.selected_box_idx = len(self.boxes) - 1
            self.mode = "select" # Tự động nhảy qua mode chỉnh sửa
            self.update()

        self.resizing_handle = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        
        # 1. Thu phóng khung nhãn nháp: Alt + Lăn chuột (Đã cải tiến độ nhạy)
        if self.alt_pressed:
            step = 6 if delta > 0 else -6
            self.draft_width = max(8, self.draft_width + step)
            self.draft_height = max(8, self.draft_height + step)
            self.update()
            
        # 2. Zoom ảnh: Ctrl + Lăn chuột
        elif self.ctrl_pressed:
            cursor_pos = event.pos()
            old_img_pos = self.canvas_to_img(cursor_pos)
            
            factor = 1.15 if delta > 0 else 0.85
            self.scale *= factor
            
            new_x = cursor_pos.x() - old_img_pos.x() * self.scale
            new_y = cursor_pos.y() - old_img_pos.y() * self.scale
            self.offset = QPointF(new_x, new_y)
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Alt:
            self.alt_pressed = True
            self.mode = "select" if self.mode == "suggest" else "suggest"
            self.update()
        elif event.key() == Qt.Key_Control:
            self.ctrl_pressed = True
        # Thêm phím tắt mở rộng thu phóng box nháp nhanh bằng phím '[' và ']'
        elif event.key() == Qt.Key_BracketRight:
            self.draft_width += 5
            self.draft_height += 5
            self.update()
        elif event.key() == Qt.Key_BracketLeft:
            self.draft_width = max(8, self.draft_width - 5)
            self.draft_height = max(8, self.draft_height - 5)
            self.update()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Alt:
            self.alt_pressed = False
        elif event.key() == Qt.Key_Control:
            self.ctrl_pressed = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLO Labeling Tool (Ảnh nhỏ 224-640)")
        self.resize(1200, 800)

        self.input_dir = ""
        self.output_dir = ""
        self.image_files = []
        self.current_img_idx = -1

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Panel trái: Vùng vẽ
        self.canvas = LabelingCanvas(self)
        layout.addWidget(self.canvas, stretch=4)

        # Panel phải: Nút bấm điều hướng & danh mục
        right_panel = QVBoxLayout()
        
        # Thư mục
        self.btn_input = QPushButton("Thư mục ảnh (Input)")
        self.btn_input.clicked.connect(self.select_input_dir)
        right_panel.addWidget(self.btn_input)

        self.btn_output = QPushButton("Thư mục nhãn (Output)")
        self.btn_output.clicked.connect(self.select_output_dir)
        right_panel.addWidget(self.btn_output)

        self.lbl_info = QLabel("Chưa chọn thư mục")
        right_panel.addWidget(self.lbl_info)

        # Quản lý danh mục nhãn
        right_panel.addWidget(QLabel("<b>Danh sách Nhãn (Classes):</b>"))
        self.class_list_widget = QListWidget()
        self.class_list_widget.currentRowChanged.connect(self.change_selected_class)
        right_panel.addWidget(self.class_list_widget)

        # Bộ nút Thêm / Sửa / Xóa Nhãn
        btn_class_layout = QHBoxLayout()
        
        btn_add_class = QPushButton("Thêm")
        btn_add_class.clicked.connect(self.add_class)
        btn_class_layout.addWidget(btn_add_class)

        btn_edit_class = QPushButton("Sửa Tên")
        btn_edit_class.clicked.connect(self.edit_class)
        btn_class_layout.addWidget(btn_edit_class)

        btn_delete_class = QPushButton("Xóa Nhãn")
        btn_delete_class.clicked.connect(self.delete_class)
        btn_class_layout.addWidget(btn_delete_class)

        right_panel.addLayout(btn_class_layout)

        # Thao tác với Bounding Box
        right_panel.addWidget(QLabel("<b>Thao tác với Bounding Box:</b>"))
        
        btn_apply = QPushButton("Gán Nhãn cho Box chọn")
        btn_apply.clicked.connect(self.apply_class_to_selected_box)
        right_panel.addWidget(btn_apply)

        btn_delete_box = QPushButton("Xóa Box đang chọn (Delete)")
        btn_delete_box.clicked.connect(self.delete_selected_box)
        right_panel.addWidget(btn_delete_box)

        # Chuyển ảnh & Lưu
        btn_save = QPushButton("Lưu nhãn (S)")
        btn_save.clicked.connect(self.save_labels)
        right_panel.addWidget(btn_save)

        btn_next = QPushButton("Ảnh tiếp (D / ->)")
        btn_next.clicked.connect(self.next_image)
        right_panel.addWidget(btn_next)

        btn_prev = QPushButton("Ảnh trước (A / <-)")
        btn_prev.clicked.connect(self.prev_image)
        right_panel.addWidget(btn_prev)

        # Bảng hướng dẫn phím tắt nhỏ
        help_lbl = QLabel(
            "<small><b>Mẹo thao tác:</b><br>"
            "• Phím <b>Alt</b>: Bật/tắt chế độ vẽ<br>"
            "• Phím <b>[</b> và <b>]</b>: Phóng to/thu nhỏ khung nháp<br>"
            "• Phím <b>Ctrl + Lăn chuột</b>: Zoom ảnh<br>"
            "• Phím <b>Delete</b>: Xóa Box chọn</small>"
        )
        right_panel.addWidget(help_lbl)

        right_panel.addStretch()
        layout.addLayout(right_panel, stretch=1)

    def select_input_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục Input chứa ảnh")
        if dir_path:
            self.input_dir = dir_path
            valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
            self.image_files = [f for f in os.listdir(dir_path) if f.lower().endswith(valid_exts)]
            self.image_files.sort()
            if self.image_files:
                self.current_img_idx = 0
                self.load_image_data()

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục Output lưu nhãn")
        if dir_path:
            self.output_dir = dir_path
            self.load_classes_txt()

    def load_image_data(self):
        if not (0 <= self.current_img_idx < len(self.image_files)):
            return
        
        filename = self.image_files[self.current_img_idx]
        img_path = os.path.join(self.input_dir, filename)
        
        boxes = []
        if self.output_dir:
            txt_filename = os.path.splitext(filename)[0] + ".txt"
            txt_path = os.path.join(self.output_dir, txt_filename)
            if os.path.exists(txt_path):
                with open(txt_path, 'r', encoding='utf-8') as f:
                    for line in f.readlines():
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            boxes.append({
                                'class_id': int(parts[0]),
                                'x_center': float(parts[1]),
                                'y_center': float(parts[2]),
                                'width': float(parts[3]),
                                'height': float(parts[4])
                            })

        self.canvas.set_image(img_path, boxes)
        self.lbl_info.setText(f"Ảnh [{self.current_img_idx + 1}/{len(self.image_files)}]: {filename}")

    def save_labels(self):
        if not self.output_dir:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn thư mục Output trước khi lưu!")
            return
        if self.current_img_idx < 0:
            return

        filename = self.image_files[self.current_img_idx]
        txt_filename = os.path.splitext(filename)[0] + ".txt"
        txt_path = os.path.join(self.output_dir, txt_filename)

        lines = []
        for b in self.canvas.boxes:
            line = f"{b['class_id']} {b['x_center']:.6f} {b['y_center']:.6f} {b['width']:.6f} {b['height']:.6f}"
            lines.append(line)

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        self.export_classes_txt()
        QMessageBox.information(self, "Thông báo", f"Đã lưu nhãn và file classes.txt!")

    def export_classes_txt(self):
        if not self.output_dir:
            return
        classes_path = os.path.join(self.output_dir, "classes.txt")
        sorted_classes = sorted(self.canvas.classes, key=lambda x: x['id'])
        class_names = [c['name'] for c in sorted_classes]
        
        with open(classes_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(class_names))

    def load_classes_txt(self):
        if not self.output_dir:
            return
        classes_path = os.path.join(self.output_dir, "classes.txt")
        if os.path.exists(classes_path):
            self.canvas.classes.clear()
            self.class_list_widget.clear()
            with open(classes_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                for idx, name in enumerate(lines):
                    new_class = {'id': idx, 'name': name}
                    self.canvas.classes.append(new_class)
            self.refresh_class_list_ui()

    def refresh_class_list_ui(self):
        """Cập nhật lại toàn bộ giao diện danh sách Class sau khi thêm/sửa/xóa"""
        self.class_list_widget.clear()
        for c in sorted(self.canvas.classes, key=lambda x: x['id']):
            self.class_list_widget.addItem(f"[{c['id']}] {c['name']}")
        
        if self.canvas.classes:
            self.class_list_widget.setCurrentRow(min(self.canvas.current_class_id, len(self.canvas.classes) - 1))

    def add_class(self):
        name, ok = QInputDialog.getText(self, "Thêm Nhãn mới", "Nhập tên nhãn:")
        if ok and name.strip():
            # Tự động gán ID theo thứ tự nối tiếp
            class_id = len(self.canvas.classes)
            new_class = {'id': class_id, 'name': name.strip()}
            self.canvas.classes.append(new_class)
            self.refresh_class_list_ui()
            self.export_classes_txt()

    def edit_class(self):
        row = self.class_list_widget.currentRow()
        if row < 0 or row >= len(self.canvas.classes):
            QMessageBox.warning(self, "Chú ý", "Vui lòng chọn 1 nhãn để đổi tên!")
            return
        
        current_class = self.canvas.classes[row]
        new_name, ok = QInputDialog.getText(
            self, "Sửa tên Nhãn", f"Đổi tên nhãn ID [{current_class['id']}]:", text=current_class['name']
        )
        if ok and new_name.strip():
            current_class['name'] = new_name.strip()
            self.refresh_class_list_ui()
            self.export_classes_txt()
            self.canvas.update()

    def delete_class(self):
        row = self.class_list_widget.currentRow()
        if row < 0 or row >= len(self.canvas.classes):
            QMessageBox.warning(self, "Chú ý", "Vui lòng chọn 1 nhãn để xóa!")
            return

        deleted_id = self.canvas.classes[row]['id']
        
        # 1. Xóa nhãn khỏi danh mục
        del self.canvas.classes[row]

        # 2. Offset lại danh sách ID liên tục (0, 1, 2...)
        for c in self.canvas.classes:
            if c['id'] > deleted_id:
                c['id'] -= 1

        # 3. Offset lại ID tương ứng trên các Box đã vẽ trong ảnh hiện tại
        new_boxes = []
        for b in self.canvas.boxes:
            if b['class_id'] == deleted_id:
                continue # Xóa luôn box thuộc nhãn vừa xóa
            elif b['class_id'] > deleted_id:
                b['class_id'] -= 1 # Offset giật lùi ID
            new_boxes.append(b)
        
        self.canvas.boxes = new_boxes
        self.canvas.selected_box_idx = -1
        
        # Cập nhật lại UI & File classes.txt
        self.refresh_class_list_ui()
        self.export_classes_txt()
        self.canvas.update()

    def change_selected_class(self, row):
        if 0 <= row < len(self.canvas.classes):
            self.canvas.current_class_id = self.canvas.classes[row]['id']

    def apply_class_to_selected_box(self):
        if self.canvas.selected_box_idx >= 0 and self.class_list_widget.currentRow() >= 0:
            box = self.canvas.boxes[self.canvas.selected_box_idx]
            box['class_id'] = self.canvas.current_class_id
            self.canvas.update()

    def delete_selected_box(self):
        if self.canvas.selected_box_idx >= 0:
            del self.canvas.boxes[self.canvas.selected_box_idx]
            self.canvas.selected_box_idx = -1
            self.canvas.update()

    def next_image(self):
        if self.current_img_idx < len(self.image_files) - 1:
            if self.output_dir:
                self.save_labels()
            self.current_img_idx += 1
            self.load_image_data()

    def prev_image(self):
        if self.current_img_idx > 0:
            if self.output_dir:
                self.save_labels()
            self.current_img_idx -= 1
            self.load_image_data()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_D, Qt.Key_Right):
            self.next_image()
        elif event.key() in (Qt.Key_A, Qt.Key_Left):
            self.prev_image()
        elif event.key() == Qt.Key_S:
            self.save_labels()
        elif event.key() == Qt.Key_Delete:
            self.delete_selected_box()
        else:
            super().keyPressEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
