Put YOLO-format training images and label files in the folders above.

Each image needs a matching .txt label file.
Each label line:
class_id center_x center_y width height

All coordinates are normalized to 0..1.

Class IDs:
0 car
1 motorcycle
2 auto
3 bus
4 truck

A practical starting target is several hundred labeled examples per class.
AI-assisted annotation is strongly recommended.
