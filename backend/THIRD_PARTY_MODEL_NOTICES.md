# Third-party model notices

## OpenCV Zoo YuNet face detector

- Model: `face_detection_yunet_2023mar.onnx`
- Upstream project: [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo/tree/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/models/face_detection_yunet)
- Pinned upstream revision: `d4938dfc9d4ec5d098bfa33e98b3f3345a236586`
- SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
- License: MIT; retain the upstream copyright and license notice when redistributing.
- Model file is downloaded during the Modal image build and SHA-256 verified. It is not committed to this repository.

The YuNet detector supplies five facial landmarks and is used here only as a separately licensed experimental comparator. Its detector outputs are not the GenD upstream SCRFD/RetinaFace outputs. Matching five-point alignment geometry does not establish detector parity or crop equivalence. YuNet-generated crops remain excluded from GenD inference until a controlled benchmark validates the substitution.

## GenD / InsightFace detector distinction

GenD's official preprocessing uses its RetinaFace wrapper with the InsightFace `buffalo_l/det_10g.onnx` SCRFD detector weights. InsightFace states that its pretrained model weights are for non-commercial research use unless separately licensed. The MIT license on GenD's repository code does not grant rights to those third-party model weights. This project does not download, bundle, or deploy those weights automatically.

References:
- [GenD official repository](https://github.com/yermandy/GenD)
- [InsightFace model and licensing guidance](https://github.com/deepinsight/insightface)
- [OpenCV Zoo YuNet license](https://github.com/opencv/opencv_zoo/blob/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/models/face_detection_yunet/LICENSE)
