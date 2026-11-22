# Detector parity benchmark

The offline benchmark compares per-frame detections from a reference face detector
with a candidate detector. Use the official GenD SCRFD/RetinaFace pipeline as the
reference only when you have authorized access to its weights and have followed its
license terms.

## Run

\`python backend/detector_parity_benchmark.py --input benchmark-input.json --output benchmark-report.json\`

The utility uses only the Python standard library. No model weights are downloaded.

## Input schema

Coordinates must be in original source-frame pixels. Each face has an \`xyxy\` box
and optionally five landmarks in this order: left eye, right eye, nose, left mouth,
right mouth.

\`\`\`json
{
  "schema_version": 1,
  "reference_detector": "gend_official_scrfd",
  "candidate_detector": "opencv_yunet",
  "coordinate_space": "source_frame_pixels",
  "frames": [
    {
      "frame_id": "clip01-frame0001",
      "width": 1920,
      "height": 1080,
      "reference_faces": [
        {
          "bbox": [410, 120, 820, 650],
          "landmarks": [[520, 300], [700, 300], [610, 410], [545, 520], [680, 520]]
        }
      ],
      "candidate_faces": [
        {
          "bbox": [415, 124, 816, 645],
          "landmarks": [[524, 302], [697, 302], [611, 409], [547, 518], [678, 518]]
        }
      ]
    }
  ]
}
\`\`\`

The video API exposes YuNet's detector box and five-point landmarks in each
frame result as \`bounding_box_xyxy\` and \`landmarks_5_xy\`. MediaPipe exposes its
five landmarks too, but its box is explicitly marked as a mesh-extent proxy, not
a detector-native bounding box. Do not treat those two box sources as identical.

## Metrics

- Greedy one-to-one face matching using the configured IoU threshold (default 0.5).
- Detection precision/recall and missed/extra face counts.
- Mean/median IoU for matched faces.
- Mean five-point landmark RMSE normalized by the reference face-box diagonal.

## Interpretation

The report always returns \`compatibility_verdict: not_validated\`. A single clip,
a high detection count, or high IoU does not certify GenD preprocessing equivalence.
A meaningful validation needs representative videos, documented reference settings,
multi-face cases, occlusion, pose/lighting/compression variation, crop comparisons,
and independent review. The benchmark does not assess classifier accuracy.
