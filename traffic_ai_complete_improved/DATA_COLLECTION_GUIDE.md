# Data Collection Guide (starting from zero)

You have no labeled data yet. Here's the fastest realistic path to a
working `vehicle_traffic.pt`, in order.

## 1. Get raw footage of your actual scene

The single most important factor for accuracy is that training images
match your real camera: same angle, height, distance, and typical
lighting. A few short clips (different times of day if possible) beats
one long clip of identical conditions.

- If you don't have camera footage yet, even a phone video from the
  roadside/overpass you plan to monitor is a reasonable starting point.
- 5-10 minutes of varied footage is enough to bootstrap from.

## 2. Auto-pre-label the easy classes

Run the included script on your footage:

    python prelabel_from_video.py your_video.mp4

This extracts frames and automatically draws boxes for **car,
motorcycle, bus, truck** using a generic pretrained model, and writes
them straight into `dataset/images/` and `dataset/labels/` in YOLO
format. It does NOT label "auto" (rickshaws) -- no off-the-shelf model
knows that class -- and it will sometimes miss or mislabel a vehicle,
especially bus vs. truck at odd angles. Treat its output as a rough
first draft, not final ground truth.

## 3. Bootstrap the "auto" class from a public dataset

Since your own footage won't have any auto-rickshaw boxes yet, borrow
some to start:

- Search Roboflow Universe (universe.roboflow.com) for `class:auto` or
  `class:auto-rikshaw` -- several YOLO-format Indian-traffic datasets
  already include an auto-rickshaw class (some include car/bus/truck
  too, which you can optionally use as extra training variety for
  those classes as well).
- Download a dataset in "YOLO" export format, take only the images and
  label lines for the auto class, and merge them into
  `dataset/images/train` (+ `val`) and `dataset/labels/train` (+ `val`),
  remapping its class ID to `2` (this project's ID for "auto" -- check
  `MODEL_CLASSES.txt`).
- This gets you a working auto detector faster, but it's trained on
  someone else's camera angle -- plan to gradually replace/augment it
  with autos labeled from your own footage as you collect more.

## 4. Review and fix in a labeling tool

Upload the `images/` + `labels/` folders (with the pre-drawn boxes) into
one of these free tools and correct/add boxes visually:

- **Roboflow** (roboflow.com) -- accepts an existing YOLO dataset,
  shows the pre-drawn boxes for editing, has an AI-assisted "smart
  polygon"/label-assist mode that speeds up drawing new boxes.
- **CVAT** (cvat.ai or self-hosted) -- more manual, but free and fully
  featured.
- **makesense.ai** -- no account needed, works entirely in-browser,
  good for smaller batches.

While reviewing, specifically look for:
- Missed or wrong boxes on **auto** and **motorcycle** (most confusable
  pair -- similar size/silhouette from a distance).
- **Bus vs. truck** mistakes from the rear or in low light.
- Partially occluded vehicles (one behind another) -- label what's
  visible; the model needs to learn these are hard cases too, not just
  clean isolated vehicles.

## 5. Know when you have "enough"

There's no fixed number, but as a practical first target:

- **300-500 images per class minimum**, with actual bounding boxes of
  that class in them (a car incidentally visible in an "auto" image
  doesn't count toward the auto target unless it's boxed).
- Weight extra effort toward whichever class is smallest/hardest --
  usually auto and motorcycle.
- More scene variety (different times of day, weather, traffic
  density, occlusion) matters more than raw image count past a few
  hundred per class.

## 6. Train and check the confusion matrix

Once `dataset/images/{train,val}` and `dataset/labels/{train,val}` are
populated:

    python train.py

After training, open
`runs/traffic/vehicle_traffic/confusion_matrix.png`. Whichever class
shows the most confusion with another is where you should add more
labeled examples next, then retrain. This loop (train -> check
confusion matrix -> add data for the weakest class -> retrain) matters
more for final accuracy than any hyperparameter tweak.
