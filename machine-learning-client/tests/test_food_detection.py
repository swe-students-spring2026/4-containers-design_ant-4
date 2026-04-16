import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestParseArgs:
    def test_required_input_flag(self):
        from food_detection import parse_args

        with patch("sys.argv", ["prog", "--input", "/some/dir"]):
            args = parse_args()
            assert args.input == "/some/dir"

    def test_default_values(self):
        from food_detection import parse_args

        with patch("sys.argv", ["prog", "-i", "/img"]):
            args = parse_args()
            assert args.output == "./results"
            assert args.box_thresh == 0.35
            assert args.text_thresh == 0.25
            assert args.device == ""
            assert args.save_crop is False

    def test_custom_values(self):
        from food_detection import parse_args

        with patch(
            "sys.argv",
            [
                "prog",
                "-i",
                "/img",
                "-o",
                "/out",
                "--classes",
                "sushi. ramen",
                "--box-thresh",
                "0.5",
                "--text-thresh",
                "0.4",
                "--device",
                "cpu",
                "--save-crop",
            ],
        ):
            args = parse_args()
            assert args.output == "/out"
            assert args.classes == "sushi. ramen"
            assert args.box_thresh == 0.5
            assert args.text_thresh == 0.4
            assert args.device == "cpu"
            assert args.save_crop is True

    def test_missing_required_input(self):
        from food_detection import parse_args

        with patch("sys.argv", ["prog"]):
            with pytest.raises(SystemExit):
                parse_args()


class TestGetImageFiles:
    def test_finds_image_files(self, tmp_path):
        from food_detection import get_image_files

        (tmp_path / "a.jpg").write_bytes(b"img")
        (tmp_path / "b.png").write_bytes(b"img")
        (tmp_path / "c.txt").write_bytes(b"txt")

        files = get_image_files(str(tmp_path))
        names = [f.name for f in files]
        assert "a.jpg" in names
        assert "b.png" in names
        assert "c.txt" not in names

    def test_nonexistent_directory(self):
        from food_detection import get_image_files

        with pytest.raises(SystemExit):
            get_image_files("/nonexistent/path/xyz")

    def test_empty_directory(self, tmp_path):
        from food_detection import get_image_files

        (tmp_path / "readme.txt").write_bytes(b"no images here")
        with pytest.raises(SystemExit):
            get_image_files(str(tmp_path))

    def test_supported_extensions(self, tmp_path):
        from food_detection import get_image_files

        for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"]:
            (tmp_path / f"img{ext}").write_bytes(b"img")

        files = get_image_files(str(tmp_path))
        assert len(files) == 7


class TestDrawDetections:
    def test_returns_copy_with_annotations(self):
        from food_detection import draw_detections

        img = np.zeros((400, 600, 3), dtype=np.uint8)
        detections = [
            {
                "class_name": "apple",
                "confidence": 0.92,
                "bbox_xyxy": [50, 50, 200, 200],
            },
        ]

        result = draw_detections(img, detections)

        assert result is not img
        assert result.shape == img.shape
        assert not np.array_equal(result, img)

    def test_empty_detections(self):
        from food_detection import draw_detections

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = draw_detections(img, [])

        assert result is not img
        np.testing.assert_array_equal(result, img)

    def test_multiple_detections(self):
        from food_detection import draw_detections

        img = np.zeros((400, 600, 3), dtype=np.uint8)
        detections = [
            {
                "class_name": "apple",
                "confidence": 0.9,
                "bbox_xyxy": [10, 10, 100, 100],
            },
            {
                "class_name": "banana",
                "confidence": 0.8,
                "bbox_xyxy": [200, 200, 350, 350],
            },
        ]

        result = draw_detections(img, detections)
        assert not np.array_equal(result, img)

    def test_same_class_reuses_color(self):
        from food_detection import draw_detections

        img = np.zeros((400, 600, 3), dtype=np.uint8)
        detections = [
            {
                "class_name": "apple",
                "confidence": 0.9,
                "bbox_xyxy": [10, 10, 100, 100],
            },
            {
                "class_name": "apple",
                "confidence": 0.7,
                "bbox_xyxy": [200, 200, 300, 300],
            },
        ]

        result = draw_detections(img, detections)
        assert result is not img


class TestLoadModel:
    def test_load_groundingdino_backend(self):
        from food_detection import load_model

        mock_model = MagicMock()
        mock_gd_module = MagicMock()
        mock_gd_module.util.inference.load_model.return_value = mock_model
        mock_gd_module.__file__ = "/fake/groundingdino/__init__.py"

        mock_config_path = MagicMock()
        mock_config_path.exists.return_value = True

        with patch.dict(
            "sys.modules",
            {
                "groundingdino": mock_gd_module,
                "groundingdino.util": mock_gd_module.util,
                "groundingdino.util.inference": mock_gd_module.util.inference,
            },
        ), patch("food_detection.Path") as mock_path_cls, patch("food_detection.torch"):
            mock_gd_dir = MagicMock()
            mock_config = MagicMock()
            mock_config.exists.return_value = True
            mock_gd_dir.__truediv__ = MagicMock(return_value=mock_config)
            (mock_gd_dir / "config").__truediv__ = MagicMock(return_value=mock_config)

            mock_weights_dir = MagicMock()
            mock_weights_path = MagicMock()
            mock_weights_path.exists.return_value = True
            mock_weights_dir.__truediv__ = MagicMock(return_value=mock_weights_path)

            mock_home = MagicMock()
            mock_path_cls.home.return_value = mock_home
            mock_home.__truediv__ = MagicMock(return_value=mock_weights_dir)

            _, backend = load_model("cpu")
            assert backend == "groundingdino"

    def test_load_transformers_backend(self):
        from food_detection import load_model

        mock_processor = MagicMock()
        mock_raw_model = MagicMock()
        # load_model calls model.to(device) — .to() returns itself
        mock_raw_model.to.return_value = mock_raw_model

        _real_import = __import__

        def _side_effect(name, *args, **kwargs):
            if "groundingdino" in name:
                raise ImportError(f"No module named '{name}'")
            if name == "transformers":
                mod = MagicMock()
                mod.AutoProcessor.from_pretrained.return_value = mock_processor
                mod.AutoModelForZeroShotObjectDetection.from_pretrained.return_value = (
                    mock_raw_model
                )
                return mod
            return _real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_side_effect):
            model, backend = load_model("cpu")
            assert backend == "transformers"
            # model is (model_after_to, processor)
            assert model == (mock_raw_model, mock_processor)

    def test_load_model_no_backend_available(self):
        from food_detection import load_model

        _real_import = __import__

        def _side_effect(name, *args, **kwargs):
            if "groundingdino" in name or name == "transformers":
                raise ImportError(f"No module named '{name}'")
            return _real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_side_effect):
            with pytest.raises(SystemExit):
                load_model("cpu")


class TestDetectBackends:
    def test_groundingdino_returns_detections_and_image(self):
        from food_detection import detect_groundingdino

        import torch

        mock_model = MagicMock()
        fake_image_source = np.zeros((480, 640, 3), dtype=np.uint8)
        fake_image_tensor = MagicMock()

        fake_boxes = torch.tensor([[0.5, 0.5, 0.2, 0.2]])
        fake_logits = torch.tensor([0.85])
        fake_phrases = ["apple"]

        mock_load_image = MagicMock(return_value=(fake_image_source, fake_image_tensor))
        mock_predict = MagicMock(return_value=(fake_boxes, fake_logits, fake_phrases))

        with patch.dict(
            "sys.modules",
            {
                "groundingdino": MagicMock(),
                "groundingdino.util": MagicMock(),
                "groundingdino.util.inference": MagicMock(
                    load_image=mock_load_image, predict=mock_predict
                ),
            },
        ):
            detections, image_bgr = detect_groundingdino(
                mock_model, "/fake/img.jpg", "apple.", 0.35, 0.25, "cpu"
            )

            assert len(detections) == 1
            assert detections[0]["class_name"] == "apple"
            assert detections[0]["confidence"] == 0.85
            assert len(detections[0]["bbox_xyxy"]) == 4
            assert image_bgr.shape == (480, 640, 3)

    def test_transformers_returns_detections_and_image(self):
        from food_detection import detect_transformers

        import torch

        mock_model = MagicMock()
        mock_processor = MagicMock()

        # PIL.Image.open() is called inside detect_transformers via
        # "from PIL import Image; image = Image.open(path).convert('RGB')"
        fake_pil_image = MagicMock()
        fake_pil_image.convert.return_value = fake_pil_image
        fake_pil_image.size = (640, 480)

        fake_np_array = np.zeros((480, 640, 3), dtype=np.uint8)

        # processor(images=..., text=..., return_tensors="pt") -> inputs
        mock_inputs = MagicMock()
        mock_inputs.input_ids = torch.tensor([[1]])
        mock_inputs.to.return_value = mock_inputs
        mock_processor.return_value = mock_inputs

        mock_processor.post_process_grounded_object_detection.return_value = [
            {
                "boxes": torch.tensor([[100.0, 50.0, 300.0, 250.0]]),
                "scores": torch.tensor([0.91]),
                "labels": ["banana"],
            }
        ]

        # Patch PIL.Image at the module level so "from PIL import Image" works
        mock_pil = MagicMock()
        mock_pil.Image.open.return_value = fake_pil_image

        with patch.dict("sys.modules", {"PIL": mock_pil, "PIL.Image": mock_pil.Image}):
            with patch(
                "food_detection.cv2.cvtColor", return_value=fake_np_array
            ), patch("food_detection.np.array", return_value=fake_np_array):
                detections, _ = detect_transformers(
                    (mock_model, mock_processor),
                    "/fake/img.jpg",
                    "banana.",
                    0.35,
                    0.25,
                    "cpu",
                )

                assert len(detections) == 1
                assert detections[0]["class_name"] == "banana"
                assert detections[0]["confidence"] == 0.91
                assert len(detections[0]["bbox_xyxy"]) == 4


def _make_args(tmp_path, **overrides):
    """Create a namespace mimicking parse_args() output."""
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    (input_dir / "food.jpg").write_bytes(b"fake")

    defaults = {
        "input": str(input_dir),
        "output": str(tmp_path / "output"),
        "classes": "apple. banana",
        "box_thresh": 0.35,
        "text_thresh": 0.25,
        "device": "cpu",
        "save_crop": False,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


class TestRunDetection:
    def test_run_detection_basic(self, tmp_path):
        from food_detection import run_detection

        args = _make_args(tmp_path)
        fake_detections = [
            {
                "class_name": "apple",
                "confidence": 0.9,
                "bbox_xyxy": [10, 10, 100, 100],
            }
        ]
        fake_image = np.zeros((200, 200, 3), dtype=np.uint8)

        mock_model = MagicMock()
        with patch(
            "food_detection.load_model", return_value=(mock_model, "groundingdino")
        ), patch(
            "food_detection.detect_groundingdino",
            return_value=(fake_detections, fake_image),
        ) as mock_detect, patch(
            "food_detection.draw_detections", return_value=fake_image
        ), patch(
            "food_detection.cv2.imwrite"
        ):
            run_detection(args)

            mock_detect.assert_called_once()
            output_dir = Path(args.output)
            assert (output_dir / "detection_results.json").exists()
            assert (output_dir / "detection_report.txt").exists()

            with open(output_dir / "detection_results.json", encoding="utf-8") as f:
                data = json.load(f)
            assert data["total_images"] == 1
            assert data["total_detections"] == 1
            assert data["backend"] == "groundingdino"

    def test_run_detection_no_detections(self, tmp_path):
        from food_detection import run_detection

        args = _make_args(tmp_path)
        fake_image = np.zeros((200, 200, 3), dtype=np.uint8)

        mock_model = MagicMock()
        with patch(
            "food_detection.load_model", return_value=(mock_model, "transformers")
        ), patch(
            "food_detection.detect_transformers", return_value=([], fake_image)
        ), patch(
            "food_detection.draw_detections", return_value=fake_image
        ), patch(
            "food_detection.cv2.imwrite"
        ):
            run_detection(args)

            output_dir = Path(args.output)
            with open(output_dir / "detection_results.json", encoding="utf-8") as f:
                data = json.load(f)
            assert data["total_detections"] == 0

    def test_run_detection_with_save_crop(self, tmp_path):
        from food_detection import run_detection

        args = _make_args(tmp_path, save_crop=True)
        fake_detections = [
            {
                "class_name": "sushi",
                "confidence": 0.88,
                "bbox_xyxy": [10, 10, 50, 50],
            }
        ]
        fake_image = np.ones((100, 100, 3), dtype=np.uint8) * 128

        mock_model = MagicMock()
        with patch(
            "food_detection.load_model", return_value=(mock_model, "groundingdino")
        ), patch(
            "food_detection.detect_groundingdino",
            return_value=(fake_detections, fake_image),
        ), patch(
            "food_detection.draw_detections", return_value=fake_image
        ), patch(
            "food_detection.cv2.imwrite"
        ) as mock_imwrite:
            run_detection(args)

            # imwrite called for annotated image + crop
            assert mock_imwrite.call_count == 2

    def test_run_detection_auto_device(self, tmp_path):
        from food_detection import run_detection

        args = _make_args(tmp_path, device="")
        fake_image = np.zeros((200, 200, 3), dtype=np.uint8)

        mock_model = MagicMock()
        with patch(
            "food_detection.load_model", return_value=(mock_model, "groundingdino")
        ), patch(
            "food_detection.detect_groundingdino", return_value=([], fake_image)
        ), patch(
            "food_detection.draw_detections", return_value=fake_image
        ), patch(
            "food_detection.cv2.imwrite"
        ), patch(
            "food_detection.torch"
        ) as mock_torch:
            mock_torch.cuda.is_available.return_value = False
            run_detection(args)

    def test_run_detection_text_prompt_trailing_dot(self, tmp_path):
        """Classes without trailing dot should get one appended."""
        from food_detection import run_detection

        args = _make_args(tmp_path, classes="apple. banana")
        fake_image = np.zeros((200, 200, 3), dtype=np.uint8)

        mock_model = MagicMock()
        with patch(
            "food_detection.load_model", return_value=(mock_model, "groundingdino")
        ), patch(
            "food_detection.detect_groundingdino", return_value=([], fake_image)
        ) as mock_detect, patch(
            "food_detection.draw_detections", return_value=fake_image
        ), patch(
            "food_detection.cv2.imwrite"
        ):
            run_detection(args)

            call_args = mock_detect.call_args
            text_prompt = call_args[0][2]  # 3rd positional arg
            assert text_prompt.endswith(".")

    def test_report_content(self, tmp_path):
        from food_detection import run_detection

        args = _make_args(tmp_path)
        fake_detections = [
            {
                "class_name": "rice",
                "confidence": 0.75,
                "bbox_xyxy": [20, 20, 80, 80],
            }
        ]
        fake_image = np.zeros((200, 200, 3), dtype=np.uint8)

        mock_model = MagicMock()
        with patch(
            "food_detection.load_model", return_value=(mock_model, "groundingdino")
        ), patch(
            "food_detection.detect_groundingdino",
            return_value=(fake_detections, fake_image),
        ), patch(
            "food_detection.draw_detections", return_value=fake_image
        ), patch(
            "food_detection.cv2.imwrite"
        ):
            run_detection(args)

            report = (Path(args.output) / "detection_report.txt").read_text()
            assert "Food Detection Report" in report
            assert "rice" in report
            # format is f"{d['confidence']:.2%}" -> "75.00%"
            assert "75.00%" in report

    def test_run_detection_multiple_images_with_transformers_backend(self, tmp_path):
        from food_detection import run_detection

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "a.jpg").write_bytes(b"fake-a")
        (input_dir / "b.png").write_bytes(b"fake-b")

        args = Namespace(
            input=str(input_dir),
            output=str(tmp_path / "output"),
            classes="apple.",
            box_thresh=0.35,
            text_thresh=0.25,
            device="cpu",
            save_crop=False,
        )
        fake_image = np.zeros((200, 200, 3), dtype=np.uint8)
        detect_results = [
            (
                [
                    {
                        "class_name": "apple",
                        "confidence": 0.9,
                        "bbox_xyxy": [10, 10, 50, 50],
                    }
                ],
                fake_image,
            ),
            ([], fake_image),
        ]

        mock_model = MagicMock()
        with patch(
            "food_detection.load_model", return_value=(mock_model, "transformers")
        ), patch(
            "food_detection.detect_transformers", side_effect=detect_results
        ) as mock_detect, patch(
            "food_detection.draw_detections", return_value=fake_image
        ), patch(
            "food_detection.cv2.imwrite"
        ):
            run_detection(args)

        assert mock_detect.call_count == 2
        assert mock_detect.call_args_list[0].args[2] == "apple."
        output_dir = Path(args.output)
        with open(output_dir / "detection_results.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["backend"] == "transformers"
        assert data["total_images"] == 2
        assert data["total_detections"] == 1


class TestConstants:
    def test_default_food_classes_not_empty(self):
        from food_detection import DEFAULT_FOOD_CLASSES

        assert len(DEFAULT_FOOD_CLASSES) > 0
        assert "rice" in DEFAULT_FOOD_CLASSES

    def test_img_extensions(self):
        from food_detection import IMG_EXTENSIONS

        assert ".jpg" in IMG_EXTENSIONS
        assert ".png" in IMG_EXTENSIONS
        assert ".txt" not in IMG_EXTENSIONS
