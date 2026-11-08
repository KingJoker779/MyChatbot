import contextlib
from io import BytesIO, StringIO
import importlib.util
import json
from pathlib import Path
import random
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import setup_runtime

SPEC = importlib.util.spec_from_file_location("chatbot", ROOT / "project 1.py")
chatbot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(chatbot)


class ChatbotRegressionTests(unittest.TestCase):
	def test_ping_conversions(self):
		self.assertIn("67,000 ms is 67 seconds", chatbot.answer_ping_time("67k ms ping"))
		self.assertIn("1 minute 7 seconds", chatbot.answer_ping_time("67,000 ms latency"))
		self.assertIn("0.5 seconds", chatbot.answer_ping_time("500 ms ping"))
		self.assertIsNone(chatbot.answer_ping_time("67k ms"))
		self.assertIsNone(chatbot.answer_ping_time("9" * 10000 + " ms ping"))

	def test_standalone_greetings_only(self):
		for greeting in ("yo", "HEY!", "hello bot", "good morning"):
			with self.subTest(greeting=greeting):
				self.assertEqual(
					chatbot.answer_greeting(greeting),
					"Hey! How can I help?",
				)
		self.assertIsNone(chatbot.answer_greeting("yo, what is 2 + 2?"))

	def test_history_round_trip_and_parent_creation(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "nested" / "history.json"
			messages = [
				{"role": "user", "content": "Hello 👋"},
				{"role": "assistant", "content": "Hey!"},
			]
			with patch.object(chatbot, "HISTORY_FILE", path):
				chatbot.save_history(messages)
				self.assertEqual(chatbot.load_history(), messages)
				self.assertFalse(path.with_suffix(".tmp").exists())

	def test_invalid_history_shapes_raise_clear_error(self):
		for content in ("[]", '{"messages":[null]}', '{"messages":[{"role":"system","content":"x"}]}'):
			with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
				path = Path(directory) / "history.json"
				path.write_text(content, encoding="utf-8")
				with patch.object(chatbot, "HISTORY_FILE", path):
					with self.assertRaisesRegex(RuntimeError, "Could not read saved chat history"):
						chatbot.load_history()

	def test_corrupt_json_history_raises_clear_error(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "history.json"
			path.write_text("{", encoding="utf-8")
			with patch.object(chatbot, "HISTORY_FILE", path):
				with self.assertRaisesRegex(RuntimeError, "Could not read saved chat history"):
					chatbot.load_history()

	def test_relevant_history_keeps_order_and_does_not_mutate_input(self):
		history = [
			{"role": "user", "content": "Roblox trains"},
			{"role": "assistant", "content": "Roblox trains carry cargo."},
			{"role": "user", "content": "Tell me about space"},
			{"role": "assistant", "content": "Stars are distant suns."},
			{"role": "user", "content": "Roblox trains and cargo"},
			{"role": "assistant", "content": "You can route cargo."},
			{"role": "user", "content": "Explain Roblox trains"},
		]
		original = json.dumps(history)
		messages = chatbot.build_messages(history)
		self.assertEqual(messages[0]["role"], "system")
		self.assertEqual(
			sum(message["role"] == "system" for message in messages),
			1,
		)
		self.assertEqual(messages[-1], history[-1])
		self.assertIn("Roblox trains carry cargo.", messages[0]["content"])
		self.assertEqual(json.dumps(history), original)

	def test_roblox_listing_and_bad_payloads(self):
		payload = {
			"searchResults": [{
				"contentGroupType": "Game",
				"contents": [{
					"name": "Overfreight!",
					"description": "Build railways and deliver freight.",
					"creatorName": "Example Studio",
					"canonicalUrlPath": "/games/123",
				}],
			}],
		}
		response = BytesIO(json.dumps(payload).encode())
		with patch.object(chatbot, "urlopen", return_value=response):
			reply = chatbot.answer_roblox_game("explain overfreight on roblox")
		self.assertIn("Build railways and deliver freight.", reply)
		self.assertIn("roblox.com/games/123", reply)
		for malformed in ('[]', '{"searchResults":[null]}', '{"searchResults":[{"contentGroupType":"Game","contents":[{"name":"Overfreight"}]}]}'):
			response = BytesIO(malformed.encode())
			with patch.object(chatbot, "urlopen", return_value=response):
				self.assertIsInstance(
					chatbot.answer_roblox_game("explain overfreight on roblox"),
					str,
				)

	def test_roblox_network_failure_does_not_crash(self):
		with patch.object(chatbot, "urlopen", side_effect=OSError("offline")):
			reply = chatbot.answer_roblox_game("explain overfreight on roblox")
		self.assertIn("couldn't reach Roblox", reply)

	def test_image_loader_rejects_bad_files_and_reads_supported_photo(self):
		with tempfile.TemporaryDirectory() as directory:
			image = Path(directory) / "photo.png"
			image.write_bytes(b"test image")
			not_image = Path(directory) / "notes.txt"
			not_image.write_text("not a photo", encoding="utf-8")
			with patch("builtins.input", side_effect=[str(not_image), f'"{image}"', ""]):
				with contextlib.redirect_stdout(StringIO()):
					result = chatbot.collect_images()
		self.assertEqual(len(result), 1)
		self.assertTrue(result[0].startswith("data:image/png;base64,"))

	def test_chatbot_shortcuts_save_history_and_quit(self):
		with tempfile.TemporaryDirectory() as directory:
			model_directory = Path(directory)
			(model_directory / "Qwen3.5-0.8B-Q4_K_M.gguf").touch()
			(model_directory / "mmproj-F16.gguf").touch()
			history_path = Path(directory) / "history.json"
			answers = iter(["yo", "67k ms ping", "/quit"])
			with (
				patch.object(chatbot, "HISTORY_FILE", history_path),
				patch.object(chatbot, "find_llama_server", return_value=Path("llama-server.exe")),
				patch.object(chatbot, "MODEL_DIR", model_directory),
				patch("builtins.input", side_effect=lambda _prompt="": next(answers)),
				contextlib.redirect_stdout(StringIO()),
			):
				chatbot.main()
			messages = json.loads(history_path.read_text(encoding="utf-8"))["messages"]
		self.assertEqual(len(messages), 4)
		self.assertEqual(messages[1]["content"], "Hey! How can I help?")
		self.assertIn("67,000 ms is 67 seconds", messages[3]["content"])

	def test_runtime_extraction_rejects_path_traversal(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			archive_path = root / "unsafe.zip"
			with zipfile.ZipFile(archive_path, "w") as archive:
				archive.writestr("../outside.txt", "unsafe")
			with patch.object(setup_runtime, "RUNTIME_DIR", root / "runtime"):
				with self.assertRaisesRegex(RuntimeError, "unsafe path"):
					setup_runtime.extract_runtime(archive_path)
			self.assertFalse((root / "outside.txt").exists())

	def test_archive_path_guard_accepts_only_contained_paths(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			self.assertTrue(setup_runtime.is_safe_archive_path(root, "bin/server.exe"))
			for unsafe in (
				"../escape",
				"/absolute",
				"C:\\outside\\file",
				"C:drive-relative",
				"file.txt:alternate-stream",
				"NUL",
				"COM1.log",
			):
				with self.subTest(unsafe=unsafe):
					self.assertFalse(setup_runtime.is_safe_archive_path(root, unsafe))

	def test_random_ping_inputs_never_overflow(self):
		randomizer = random.Random(891)
		for _ in range(5000):
			digits = "".join(
				randomizer.choices("0123456789", k=randomizer.randrange(1, 1500))
			)
			suffix = randomizer.choice(("ms", "msec", "milliseconds"))
			prefix = randomizer.choice(("ping", "latency", "delay", ""))
			result = chatbot.answer_ping_time(f"{digits} {suffix} {prefix}")
			self.assertTrue(result is None or isinstance(result, str))
			if result:
				self.assertNotIn("inf", result.lower())

	def test_streamed_chat_assembles_content_and_image_payload(self):
		chunks = [
			{"choices": [{"delta": {"content": "Hello "}}]},
			{"choices": [{"delta": {"content": "there!"}}]},
		]
		response = BytesIO(
			"".join(
				f"data: {json.dumps(chunk)}\n\n"
				for chunk in chunks
			).encode() + b"data: [DONE]\n"
		)
		messages = [{"role": "user", "content": "What is in this image?"}]
		with (
			patch.object(chatbot, "ensure_local_model_ready"),
			patch.object(chatbot, "urlopen", return_value=response) as open_url,
			contextlib.redirect_stdout(StringIO()),
		):
			reply = chatbot.request_chat(
				messages,
				images=["data:image/png;base64,AA=="],
				stream=True,
			)
		self.assertEqual(reply, "Hello there!")
		self.assertEqual(messages[0]["content"], "What is in this image?")
		payload = json.loads(open_url.call_args.args[0].data)
		self.assertEqual(payload["messages"][-1]["content"][1]["type"], "image_url")

	def test_malformed_stream_events_raise_controlled_error(self):
		events = (
			{"choices": [{"delta": None}]},
			{"choices": [{"delta": []}]},
			{"choices": [None]},
			{"choices": "not a list"},
			[],
		)
		for event in events:
			with self.subTest(event=event):
				response = BytesIO(f"data: {json.dumps(event)}\n".encode())
				with (
					patch.object(chatbot, "ensure_local_model_ready"),
					patch.object(chatbot, "urlopen", return_value=response),
					contextlib.redirect_stdout(StringIO()),
					self.assertRaisesRegex(RuntimeError, "invalid stream event"),
				):
					chatbot.request_chat(
						[{"role": "user", "content": "test"}],
						stream=True,
					)

	def test_non_stream_chat_response_and_shape_validation(self):
		valid = {"choices": [{"message": {"content": "  A clear answer.  "}}]}
		response = BytesIO(json.dumps(valid).encode())
		with (
			patch.object(chatbot, "ensure_local_model_ready"),
			patch.object(chatbot, "urlopen", return_value=response),
		):
			self.assertEqual(
				chatbot.request_chat([{"role": "user", "content": "test"}]),
				"A clear answer.",
			)

		for malformed in ([], {"choices": []}, {"choices": [None]}, {"choices": [{"message": None}]}):
			with self.subTest(malformed=malformed):
				response = BytesIO(json.dumps(malformed).encode())
				with (
					patch.object(chatbot, "ensure_local_model_ready"),
					patch.object(chatbot, "urlopen", return_value=response),
					self.assertRaisesRegex(RuntimeError, "invalid reply"),
				):
					chatbot.request_chat([{"role": "user", "content": "test"}])

	def test_invalid_utf8_from_chat_engine_is_reported_as_runtime_error(self):
		for stream, content in ((False, b"\xff"), (True, b"data: \xff\n")):
			with self.subTest(stream=stream):
				response = BytesIO(content)
				with (
					patch.object(chatbot, "ensure_local_model_ready"),
					patch.object(chatbot, "urlopen", return_value=response),
					contextlib.redirect_stdout(StringIO()),
					self.assertRaisesRegex(RuntimeError, "not valid UTF-8"),
				):
					chatbot.request_chat(
						[{"role": "user", "content": "test"}],
						stream=stream,
					)

	def test_malformed_runtime_release_metadata_is_reported(self):
		for payload in ([], {"assets": None}, {"assets": [None]}):
			with self.subTest(payload=payload), patch.object(
				setup_runtime,
				"request_bytes",
				return_value=json.dumps(payload).encode(),
			):
				with self.assertRaisesRegex(RuntimeError, "unexpected response|does not provide"):
					setup_runtime.get_runtime_asset()

	def test_runtime_release_rejects_bad_urls_digests_and_sizes(self):
		asset_name = "llama-b12193-bin-win-cpu-x64.zip"
		bad_assets = (
			{"browser_download_url": "file:///payload", "digest": "sha256:" + "a" * 64, "size": 1},
			{"browser_download_url": "https://example.invalid/payload", "digest": "sha256:" + "a" * 64, "size": 1},
			{"browser_download_url": "https://github.com/ggml-org/llama.cpp/releases/download/tag/file.zip", "digest": 1, "size": 1},
			{"browser_download_url": "https://github.com/ggml-org/llama.cpp/releases/download/tag/file.zip", "digest": "sha256:bad", "size": 1},
			{"browser_download_url": "https://github.com/ggml-org/llama.cpp/releases/download/tag/file.zip", "digest": "sha256:" + "a" * 64, "size": True},
		)
		for asset in bad_assets:
			payload = {"assets": [{"name": asset_name, **asset}]}
			with self.subTest(asset=asset), patch.object(
				setup_runtime,
				"request_bytes",
				return_value=json.dumps(payload).encode(),
			):
				with self.assertRaisesRegex(RuntimeError, "invalid"):
					setup_runtime.get_runtime_asset()

	def test_zip_extraction_rejects_links_and_bad_checksums(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			link_archive = root / "link.zip"
			link = zipfile.ZipInfo("linked-file")
			link.create_system = 3
			link.external_attr = (stat.S_IFLNK | 0o777) << 16
			with zipfile.ZipFile(link_archive, "w") as archive:
				archive.writestr(link, "../outside.txt")
			with patch.object(setup_runtime, "RUNTIME_DIR", root / "link-runtime"):
				with self.assertRaisesRegex(RuntimeError, "unsafe path or file type"):
					setup_runtime.extract_runtime(link_archive)

			damaged_archive = root / "damaged.zip"
			with zipfile.ZipFile(damaged_archive, "w") as archive:
				archive.writestr("payload.bin", b"original payload")
			with zipfile.ZipFile(damaged_archive) as archive:
				offset = archive.getinfo("payload.bin").header_offset
			with damaged_archive.open("r+b") as archive:
				archive.seek(offset + 30 + len("payload.bin"))
				byte = archive.read(1)
				archive.seek(offset + 30 + len("payload.bin"))
				archive.write(bytes([byte[0] ^ 0xFF]))
			with patch.object(setup_runtime, "RUNTIME_DIR", root / "damaged-runtime"):
				with self.assertRaisesRegex(RuntimeError, "damaged"):
					setup_runtime.extract_runtime(damaged_archive)

	def test_random_roblox_payloads_are_handled_without_uncaught_errors(self):
		randomizer = random.Random(1201)
		for _ in range(500):
			payload = randomizer.choice([
				None,
				[],
				{"searchResults": randomizer.choice([None, {}, "bad", [None]])},
				{
					"searchResults": [{
						"contentGroupType": "Game",
						"contents": randomizer.choice([
							None,
							{},
							[None],
							[{"name": randomizer.choice(["", "Overfreight", 1, None])}],
							[{
								"name": "Overfreight!",
								"description": randomizer.choice([None, {}, 42, "Game details"]),
								"creatorName": randomizer.choice([None, [], "Studio"]),
								"canonicalUrlPath": randomizer.choice([None, 42, "/games/123"]),
							}],
						]),
					}],
				},
			])
			response = BytesIO(json.dumps(payload).encode())
			with patch.object(chatbot, "urlopen", return_value=response):
				answer = chatbot.answer_roblox_game(
					"explain overfreight on roblox"
				)
			self.assertIsInstance(answer, str)
			self.assertNotIn("None", answer)

	def test_seeded_random_chat_histories_do_not_break_context_selection(self):
		randomizer = random.Random(731)
		words = ("roblox", "train", "ping", "explain", "music", "game", "hello")
		for _ in range(500):
			history = []
			for index in range(randomizer.randrange(1, 45)):
				history.append({
					"role": "user" if index % 2 == 0 else "assistant",
					"content": " ".join(
						randomizer.choices(words, k=randomizer.randrange(0, 30))
					),
				})
			result = chatbot.build_messages(history)
			self.assertEqual(result[0]["role"], "system")
			self.assertEqual(result[-1], history[-1])


if __name__ == "__main__":
	unittest.main()
