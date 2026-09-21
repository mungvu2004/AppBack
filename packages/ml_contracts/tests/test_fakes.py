"""Bộ giả (M01): cùng ảnh → cùng đầu ra; trang tổng hợp nguyên vẹn → đáp án; ảnh khác → rỗng."""

import numpy as np

from packages.ml_contracts.fakes import FakeObjectDetector, FakeTextReader, FakeWallSegmenter, answer_for
from packages.ml_contracts.ports import ObjectDetector, TextReader, WallSegmenter
from packages.ml_contracts.synthetic import render_plan


def test_fakes_m01_same_input() -> None:
    plan = render_plan(321)
    segmenter: WallSegmenter = FakeWallSegmenter()
    detector: ObjectDetector = FakeObjectDetector()
    reader: TextReader = FakeTextReader()
    image = np.array(plan.pixels)
    assert np.array_equal(segmenter.segment(image), plan.walls_mask)
    assert detector.detect(image) == plan.detections == detector.detect(image)
    assert reader.read(image) == plan.texts == reader.read(image)
    assert answer_for(image) is answer_for(np.array(plan.pixels))

    blank = np.full_like(image, 255)
    cropped = np.ascontiguousarray(image[:, :-10])
    for other in (blank, cropped, np.ascontiguousarray(image[10:])):
        assert not segmenter.segment(other).any()
        assert segmenter.segment(other).shape == other.shape[:2]
        assert detector.detect(other) == ()
        assert reader.read(other) == ()
