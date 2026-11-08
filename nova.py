"""A free, local chatbot with its own AI engine, photo input, and saved history."""

import base64
import atexit
from difflib import SequenceMatcher
import getpass
import importlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import webbrowser

LOCAL_API_URL = "http://127.0.0.1:11435/v1/chat/completions"
MODEL = "Qwen3.5-0.8B-Q4_K_M"
LOCAL_APP_DATA_DIR = Path(
	os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
)
DEFAULT_DATA_DIR = LOCAL_APP_DATA_DIR / "Nova"
LEGACY_DEFAULT_DATA_DIR = LOCAL_APP_DATA_DIR / "MyChatbot"
APP_DATA_DIR = Path(
	os.environ.get(
		"NOVA_DATA_DIR",
		os.environ.get(
			"CHATBOT_DATA_DIR",
			str(
				DEFAULT_DATA_DIR
				if getattr(sys, "frozen", False)
				else Path(__file__).resolve().parent
			),
		),
	)
)
os.environ.setdefault("NOVA_DATA_DIR", str(APP_DATA_DIR))
HISTORY_FILE = APP_DATA_DIR / "bot_history.json"
RUNTIME_DIR = APP_DATA_DIR / "runtime"
MODEL_DIR = APP_DATA_DIR / "models"
SERVER_LOG = RUNTIME_DIR / "llama-server.log"
GENERATED_IMAGES_DIR = APP_DATA_DIR / "generated_images"
IMAGE_API_URL = (
	"https://generativelanguage.googleapis.com/v1beta/models/"
	"gemini-2.5-flash-image:generateContent"
)
KEEP_RECENT_MESSAGES = 4
RELEVANT_OLD_MESSAGES = 3
RELEVANT_MESSAGE_CHARS = 220
STOP_WORDS = {
	"a", "about", "am", "an", "and", "are", "as", "at", "be", "but",
	"by", "did", "do", "for", "from", "had", "has", "have", "how", "i",
	"in", "is", "it", "me", "my", "of", "on", "or", "our", "please",
	"say", "said", "tell", "that", "the", "their", "them", "there",
	"this", "to", "us", "was", "we", "were", "what", "when", "where",
	"which", "who", "why", "with", "you", "your",
}

SYSTEM_PROMPT = (
	"You are a general-purpose assistant. Help with questions and tasks across "
	"topics, including explanations, writing, ideas, math, coding, and "
	"conversation. Answer directly and clearly; be concise unless more detail "
	"is requested. Do not invent facts or pretend to be certain: say when you "
	"are unsure and ask for missing details only when needed. For Roblox "
	"questions, do not make up game mechanics."
)

LLAMA_PROCESS = None


def migrate_legacy_data_directory(source, destination):
	if destination.exists() or not source.exists():
		return False
	try:
		source.rename(destination)
	except OSError as error:
		raise RuntimeError(
			f"Could not move existing Nova data from {source} to {destination}: {error}"
		) from error
	return True


def migrate_legacy_app_data():
	if (
		os.name == "nt"
		and getattr(sys, "frozen", False)
		and APP_DATA_DIR == DEFAULT_DATA_DIR
	):
		migrate_legacy_data_directory(
			LEGACY_DEFAULT_DATA_DIR,
			DEFAULT_DATA_DIR,
		)


def find_llama_server():
	server_name = "llama-server.exe" if os.name == "nt" else "llama-server"
	return next(RUNTIME_DIR.rglob(server_name), None) if RUNTIME_DIR.exists() else None


def local_server_error():
	if not SERVER_LOG.is_file():
		return ""
	try:
		lines = SERVER_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
	except OSError:
		return ""
	details = "\n".join(lines[-12:]).strip()
	return f"\nAI engine log:\n{details}" if details else ""


def ensure_local_model_ready():
	global LLAMA_PROCESS

	server = find_llama_server()
	model = MODEL_DIR / "Qwen3.5-0.8B-Q4_K_M.gguf"
	projector = MODEL_DIR / "mmproj-F16.gguf"
	if server is None or not model.is_file() or not projector.is_file():
		raise RuntimeError(
			"Nova's AI engine or model is missing. Run "
			"Setup Nova.bat or setup-nova.sh once."
		)
	if LLAMA_PROCESS is not None and LLAMA_PROCESS.poll() is None:
		try:
			with urlopen("http://127.0.0.1:11435/health", timeout=1):
				return
		except URLError:
			pass

	try:
		SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)
		with SERVER_LOG.open("wb") as log_file:
			LLAMA_PROCESS = subprocess.Popen(
				[
					str(server),
					"--model", str(model),
					"--mmproj", str(projector),
					"--host", "127.0.0.1",
					"--port", "11435",
					"--ctx-size", "2048",
					"--parallel", "1",
					"--threads", str(os.cpu_count() or 1),
					"--threads-batch", str(os.cpu_count() or 1),
					"--image-min-tokens", "1024",
					"--reasoning", "off",
					"--no-webui",
				],
				cwd=str(server.parent),
				stdin=subprocess.DEVNULL,
				stdout=log_file,
				stderr=subprocess.STDOUT,
				creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
			)
	except OSError as error:
		raise RuntimeError(f"Could not start the bundled AI engine: {error}") from error
	atexit.register(stop_local_model)

	deadline = time.monotonic() + 120
	while time.monotonic() < deadline:
		if LLAMA_PROCESS.poll() is not None:
			raise RuntimeError(
				"The bundled AI engine stopped before it was ready."
				+ local_server_error()
			)
		try:
			with urlopen("http://127.0.0.1:11435/health", timeout=1):
				return
		except URLError:
			time.sleep(0.5)
	raise RuntimeError(
		"The bundled AI engine did not finish starting in time."
		+ local_server_error()
	)


def stop_local_model():
	if LLAMA_PROCESS is not None and LLAMA_PROCESS.poll() is None:
		LLAMA_PROCESS.terminate()
		try:
			LLAMA_PROCESS.wait(timeout=5)
		except subprocess.TimeoutExpired:
			LLAMA_PROCESS.kill()
			LLAMA_PROCESS.wait()


def ensure_local_setup():
	server = find_llama_server()
	model = MODEL_DIR / "Qwen3.5-0.8B-Q4_K_M.gguf"
	projector = MODEL_DIR / "mmproj-F16.gguf"
	if server is not None and model.is_file() and projector.is_file():
		return True

	print("First-time setup: downloading the local AI engine and model (~740 MB).")
	print("This needs internet and about 1 GB of free storage.")
	try:
		setup_runtime = importlib.import_module("setup_runtime")
		if setup_runtime.main() != 0:
			return False
	except (ImportError, OSError, RuntimeError) as error:
		print(f"Nova: First-time setup failed: {error}")
		return False
	return True


def request_chat(messages, images=None, stream=False):
	status_stop = threading.Event()
	status_lock = threading.Lock()
	status_visible = False
	response_started = False
	status_thread = None

	request_messages = [dict(message) for message in messages]
	if images and request_messages:
		last_message = request_messages[-1]
		text = last_message.get("content", "")
		last_message["content"] = (
			[{"type": "text", "text": str(text)}]
			+ [
				{"type": "image_url", "image_url": {"url": image}}
				for image in images
			]
		)

	last_user_message = next(
		(
			str(message.get("content", ""))
			for message in reversed(messages)
			if message.get("role") == "user"
		),
		"",
	)
	max_tokens = (
		384
		if re.search(
			r"\b(?:explain|details?|steps?|examples?|compare|thorough|in depth|"
			r"write|create|story|essay|code|program|how to)\b",
			last_user_message,
			re.IGNORECASE,
		)
		else 192
	)
	payload = {
		"model": "local",
		"messages": request_messages,
		"stream": stream,
		"max_tokens": max_tokens,
	}
	request = Request(
		LOCAL_API_URL,
		data=json.dumps(payload).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	if stream:
		def show_status():
			nonlocal status_visible
			frames = ("Bot is thinking.", "Bot is thinking..", "Bot is thinking...")
			index = 0
			while not status_stop.is_set():
				with status_lock:
					if status_stop.is_set():
						break
					print("\r" + frames[index].ljust(24), end="", flush=True)
					status_visible = True
				index = (index + 1) % len(frames)
				status_stop.wait(0.5)

		status_thread = threading.Thread(target=show_status, daemon=True)
		status_thread.start()

	try:
		ensure_local_model_ready()
		with urlopen(request, timeout=300) as response:
			if not stream:
				data = json.loads(response.read().decode("utf-8"))
				if not isinstance(data, dict):
					raise RuntimeError("The local AI engine returned an invalid reply.")
				if "error" in data:
					raise RuntimeError(data["error"])
				choices = data.get("choices")
				if (
					not isinstance(choices, list)
					or not choices
					or not isinstance(choices[0], dict)
				):
					raise RuntimeError("The local AI engine returned an invalid reply.")
				message = choices[0].get("message", {})
				if not isinstance(message, dict):
					raise RuntimeError("The local AI engine returned an invalid reply.")
				reply = message.get("content", "")
				if not isinstance(reply, str):
					raise RuntimeError("The local AI engine returned an invalid reply.")
				reply = reply.strip()
				if not reply:
					raise RuntimeError("The local model returned an empty reply.")
				return reply

			parts = []
			for line in response:
				line = line.decode("utf-8").strip()
				if not line.startswith("data:"):
					continue
				event_data = line[5:].strip()
				if event_data == "[DONE]":
					continue
				event = json.loads(event_data)
				if not isinstance(event, dict):
					raise RuntimeError("The local AI engine returned an invalid stream event.")
				if "error" in event:
					raise RuntimeError(event["error"])
				choices = event.get("choices", [])
				if not isinstance(choices, list):
					raise RuntimeError("The local AI engine returned an invalid stream event.")
				if choices and not isinstance(choices[0], dict):
					raise RuntimeError("The local AI engine returned an invalid stream event.")
				delta = choices[0].get("delta", {}) if choices else {}
				if not isinstance(delta, dict):
					raise RuntimeError("The local AI engine returned an invalid stream event.")
				text = delta.get("content", "")
				if text is None:
					text = ""
				if not isinstance(text, str):
					raise RuntimeError("The local AI engine returned an invalid stream event.")
				if text:
					with status_lock:
						if not response_started:
							status_stop.set()
							if status_visible:
								print("\r" + " " * 24 + "\r", end="", flush=True)
								status_visible = False
							print("Nova: ", end="", flush=True)
							response_started = True
						print(text, end="", flush=True)
					parts.append(text)
			reply = "".join(parts).strip()
			if not reply:
				raise RuntimeError("The local model returned an empty reply.")
			return reply
	except HTTPError as error:
		details = error.read().decode("utf-8", "replace").strip()
		raise RuntimeError(
			f"The local AI engine returned HTTP {error.code}: "
			f"{details or error.reason}"
		) from error
	except UnicodeDecodeError as error:
		raise RuntimeError(
			"The local AI engine returned a response that was not valid UTF-8."
		) from error
	except URLError as error:
		raise RuntimeError(
			"The bundled AI engine is not responding. Run setup again if it "
			"keeps failing." + local_server_error()
		) from error
	finally:
		if status_thread is not None:
			status_stop.set()
			status_thread.join()
			with status_lock:
				if status_visible:
					print("\r" + " " * 24 + "\r", end="", flush=True)


def is_image_generation_request(message):
	return bool(
		re.search(
			r"\b(?:make|create|generate|draw|paint|design)\b.{0,80}"
			r"\b(?:image|picture|photo|illustration|artwork|logo|wallpaper|portrait)\b"
			r"|\b(?:image|picture|photo|illustration|artwork|logo|wallpaper|portrait)\b"
			r"\s+of\b",
			message,
			re.IGNORECASE | re.DOTALL,
		)
	)


def generate_image(prompt, api_key):
	if not api_key or not api_key.strip():
		raise RuntimeError(
			"Image creation needs your own Google AI Studio API key. "
			"Get one at https://aistudio.google.com/apikey."
		)
	if len(prompt) > 4000:
		raise RuntimeError("Image prompts must be 4,000 characters or fewer.")

	payload = {
		"contents": [{"parts": [{"text": prompt}]}],
		"generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
	}
	request = Request(
		IMAGE_API_URL,
		data=json.dumps(payload).encode("utf-8"),
		headers={
			"Content-Type": "application/json",
			"x-goog-api-key": api_key.strip(),
		},
		method="POST",
	)
	try:
		with urlopen(request, timeout=180) as response:
			data = json.loads(response.read().decode("utf-8"))
	except HTTPError as error:
		details = error.read().decode("utf-8", "replace").strip()
		try:
			error_data = json.loads(details)
			details = error_data.get("error", {}).get("message", details)
		except (json.JSONDecodeError, AttributeError):
			pass
		raise RuntimeError(
			f"Google image generation returned HTTP {error.code}: "
			f"{details or error.reason}"
		) from error
	except (URLError, TimeoutError) as error:
		raise RuntimeError(f"Could not connect to Google image generation: {error}") from error
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise RuntimeError("Google image generation returned invalid JSON.") from error

	if not isinstance(data, dict):
		raise RuntimeError("Google image generation returned an invalid response.")
	candidates = data.get("candidates")
	if not isinstance(candidates, list):
		error = data.get("error", {})
		message = error.get("message") if isinstance(error, dict) else None
		raise RuntimeError(message or "Google did not return an image.")
	for candidate in candidates:
		if not isinstance(candidate, dict):
			continue
		content = candidate.get("content")
		parts = content.get("parts") if isinstance(content, dict) else None
		if not isinstance(parts, list):
			continue
		for part in parts:
			if not isinstance(part, dict):
				continue
			image_data = part.get("inlineData", part.get("inline_data"))
			if not isinstance(image_data, dict):
				continue
			mime_type = image_data.get("mimeType", image_data.get("mime_type"))
			encoded = image_data.get("data")
			if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
				continue
			if not isinstance(encoded, str):
				continue
			try:
				image_bytes = base64.b64decode(encoded, validate=True)
			except (ValueError, base64.binascii.Error) as error:
				raise RuntimeError("Google returned invalid image data.") from error
			if image_bytes:
				return mime_type, image_bytes
	raise RuntimeError("Google's response did not contain a generated image.")


def save_generated_image(mime_type, image_bytes):
	extensions = {
		"image/png": ".png",
		"image/jpeg": ".jpg",
		"image/webp": ".webp",
	}
	extension = extensions.get(mime_type)
	if extension is None:
		raise RuntimeError("Google returned an unsupported image format.")
	try:
		GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
		image_path = GENERATED_IMAGES_DIR / f"nova-{uuid.uuid4().hex}{extension}"
		image_path.write_bytes(image_bytes)
	except OSError as error:
		raise RuntimeError(f"Could not save the generated picture: {error}") from error
	return image_path


def load_history():
	if not HISTORY_FILE.exists():
		return []

	try:
		data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
		if not isinstance(data, dict):
			raise ValueError("history must be an object")
		messages = data.get("messages", [])
		if not isinstance(messages, list):
			raise ValueError("history must contain a message list")
		for index, message in enumerate(messages):
			if (
				not isinstance(message, dict)
				or message.get("role") not in {"user", "assistant"}
				or not isinstance(message.get("content"), str)
			):
				raise ValueError(f"history message {index + 1} is invalid")
		return messages
	except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
		raise RuntimeError(f"Could not read saved chat history: {error}") from error


def save_history(messages):
	data = {"messages": messages}
	temporary_file = HISTORY_FILE.with_suffix(".tmp")
	try:
		HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
		temporary_file.write_text(
			json.dumps(data, ensure_ascii=False, indent=2),
			encoding="utf-8",
		)
		temporary_file.replace(HISTORY_FILE)
	except OSError as error:
		raise RuntimeError(f"Could not save chat history: {error}") from error


def build_messages(history):
	messages = [{"role": "system", "content": SYSTEM_PROMPT}]
	recent = history[-KEEP_RECENT_MESSAGES:]
	older = history[:-KEEP_RECENT_MESSAGES]
	query = str(history[-1].get("content", "")) if history else ""
	query_words = {
		word for word in re.findall(r"\w+", query.lower())
		if len(word) > 2 and word not in STOP_WORDS
	}

	matches = []
	for index, message in enumerate(older):
		content = message.get("content", "")
		if not isinstance(content, str):
			continue
		message_words = set(re.findall(r"\w+", content.lower()))
		score = len(query_words & message_words)
		if score:
			matches.append((score, index, message))

	if matches:
		matches.sort(key=lambda match: (match[0], match[1]), reverse=True)
		selected = sorted(matches[:RELEVANT_OLD_MESSAGES], key=lambda match: match[1])
	elif older:
		selected = [(0, index, message) for index, message in enumerate(older[-2:], start=len(older) - 2)]
	else:
		selected = []

	if selected:
		snippets = []
		for _, _, message in selected:
			content = str(message.get("content", "")).replace("\n", " ")
			if len(content) > RELEVANT_MESSAGE_CHARS:
				content = content[:RELEVANT_MESSAGE_CHARS] + "..."
			snippets.append(f"{message.get('role', 'chat')}: {content}")
		messages[0]["content"] += (
			"\n\nRelevant earlier chat excerpts, retrieved by matching words. "
			"They are partial; do not treat them as a complete record:\n"
			+ "\n".join(snippets)
		)
	messages.extend(recent)
	return messages


def answer_ping_time(message):
	if not re.search(r"\b(?:ping|latency)\b", message, re.IGNORECASE):
		return None

	match = re.search(
		r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k)?\s*"
		r"(?:ms|msec|milliseconds?)\b",
		message,
		re.IGNORECASE,
	)
	if not match:
		return None

	milliseconds = float(match.group(1).replace(",", ""))
	if match.group(2):
		milliseconds *= 1000
	if not math.isfinite(milliseconds) or milliseconds > 1e15:
		return None
	seconds = milliseconds / 1000
	total_seconds = round(seconds)
	minutes, remaining_seconds = divmod(total_seconds, 60)
	converted = (
		f"{minutes} minute{'s' if minutes != 1 else ''} "
		f"{remaining_seconds} second{'s' if remaining_seconds != 1 else ''}"
		if minutes
		else ""
	)
	duration = f"{seconds:g} seconds"
	if converted:
		duration += f" ({converted})"
	return (
		f"{milliseconds:,.0f} ms is {duration}. That is extremely high ping."
	)


def answer_greeting(message):
	greeting = (
		r"(?:hi+|hello+|hey+|yo+|hiya|howdy|sup|what(?:'s| is) up|"
		r"good morning|good afternoon|good evening)"
		r"(?:\s+(?:there|bot|assistant))?[.!?,\s]*"
	)
	if re.fullmatch(greeting, message.strip(), re.IGNORECASE):
		return "Hey! How can I help?"
	return None


def answer_roblox_game(message):
	if not re.search(r"\broblox\b", message, re.IGNORECASE):
		return None
	if not re.search(
		r"\b(?:explain|describe|define|meaning of|what is|what does|tell me about)\b",
		message,
		re.IGNORECASE,
	):
		return None

	match = re.search(
		r"\b(?:explain|describe|define|what is|what does|meaning of|tell me about)\s+"
		r"(?:me\s+)?(.+?)\s+(?:on|in)\s+roblox\b",
		message,
		re.IGNORECASE,
	)
	if not match:
		return None

	term = match.group(1).strip(" \t?!.,")
	term = re.sub(r"^(?:the\s+)?(?:game|experience)\s+", "", term, flags=re.IGNORECASE)
	term = re.sub(r"\s+(?:game|experience)$", "", term, flags=re.IGNORECASE)
	if not term:
		return None

	search_url = "https://apis.roblox.com/search-api/omni-search?" + urlencode({
		"searchQuery": term,
		"sessionId": "0",
		"contentType": "Games",
		"sortOrder": "Relevance",
	})
	request = Request(
		search_url,
		headers={"Accept": "application/json", "User-Agent": "LocalChatbot/1.0"},
	)
	try:
		with urlopen(request, timeout=8) as response:
			results = json.loads(response.read().decode("utf-8"))
	except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError):
		return (
			"I couldn't reach Roblox's game search to verify that title, so I "
			"don't want to guess. Please try again or send the Roblox game link."
		)

	if not isinstance(results, dict) or not isinstance(results.get("searchResults"), list):
		return "Roblox returned an unexpected search response, so I couldn't verify that game."

	normalized_term = re.sub(r"[^a-z0-9]", "", term.lower())
	candidates = [
		game
		for group in results.get("searchResults", [])
		if isinstance(group, dict)
		if group.get("contentGroupType") == "Game"
		for game in (
			group.get("contents")
			if isinstance(group.get("contents"), list)
			else []
		)
		if isinstance(game, dict)
		if isinstance(game.get("name"), str)
		if game["name"].strip()
	]
	game = max(
		candidates,
		key=lambda item: SequenceMatcher(
			None,
			normalized_term,
			re.sub(r"[^a-z0-9]", "", item["name"].lower()),
		).ratio(),
		default=None,
	)
	if game is None:
		return (
			f"I couldn't find a Roblox game matching '{term}'. If you send its "
			"Roblox link, I can explain the right one."
		)

	match_score = SequenceMatcher(
		None,
		normalized_term,
		re.sub(r"[^a-z0-9]", "", game["name"].lower()),
	).ratio()
	if match_score < 0.65:
		return (
			f"I couldn't confidently match '{term}' to a Roblox game. Send the "
			"game's Roblox link or exact title so I don't explain the wrong one."
		)

	name = game["name"]
	description = game.get("description", "")
	if not isinstance(description, str):
		description = ""
	description = re.sub(r"\s+", " ", description).strip()
	creator = game.get("creatorName")
	if not isinstance(creator, str):
		creator = ""
	game_path = game.get("canonicalUrlPath")
	if not isinstance(game_path, str) or not game_path.startswith("/"):
		game_path = f"/games/{game.get('rootPlaceId', '')}"
	game_url = "https://www.roblox.com" + game_path
	if not description:
		return (
			f"I found **{name}** on Roblox, but its listing doesn't include a "
			f"description, so I can't explain its gameplay reliably. {game_url}"
		)
	return (
		f"Roblox lists **{name}** as: {description}"
		+ (f" Creator: {creator}." if creator else "")
		+ f" {game_url}"
	)


def collect_images():
	images = []
	while True:
		try:
			path_text = input("Photo path (press Enter when done): ").strip()
		except (EOFError, KeyboardInterrupt):
			print()
			return []
		if not path_text:
			break

		path = Path(path_text.strip('"'))
		try:
			content_type, _ = mimetypes.guess_type(path.name)
			if content_type not in {"image/jpeg", "image/png", "image/webp"}:
				print("Nova: Please choose a JPEG, PNG, or WebP photo.")
				continue
			image_data = base64.b64encode(path.read_bytes()).decode("ascii")
			images.append(f"data:{content_type};base64,{image_data}")
		except OSError as error:
			print(f"Nova: Can't read that photo: {error}")
	return images


def main():
	try:
		migrate_legacy_app_data()
		history = load_history()
	except RuntimeError as error:
		print(f"Nova: {error}")
		return

	print(f"Nova: Local text chat uses {MODEL}; image creation uses Google's online service.")
	print("Nova: Ask me about any topic. Type /image to add photos, /clear to forget this chat, or /quit to exit.")
	print("Nova: Chat history stays on this PC; older messages are searched for relevant context.")

	while True:
		try:
			message = input("You: ").strip()
		except (EOFError, KeyboardInterrupt):
			print("\nNova: Goodbye!")
			break

		if message.lower() in {"/quit", "quit", "exit", "bye"}:
			print("Nova: Goodbye!")
			break
		if message.lower() == "/clear":
			history = []
			try:
				save_history(history)
			except RuntimeError as error:
				print(f"Nova: {error}")
			else:
				print("Nova: Chat history cleared.")
			continue

		images = collect_images() if message.lower() == "/image" else []
		if message.lower() == "/image":
			if not images:
				continue
			try:
				message = input("What would you like to know about the photos? ").strip()
			except (EOFError, KeyboardInterrupt):
				print()
				continue
			if not message:
				message = "Describe these photos."

		if not message:
			continue

		history.append({"role": "user", "content": message})
		reply = None
		generate_picture = not images and is_image_generation_request(message)
		if generate_picture:
			image_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
			if not image_api_key:
				try:
					image_api_key = getpass.getpass(
						"Google AI Studio API key (input hidden): "
					).strip()
				except (EOFError, KeyboardInterrupt):
					print("\nNova: Image creation cancelled.")
					history.pop()
					continue
			if not image_api_key:
				print("Nova: No image API key entered; image creation cancelled.")
				history.pop()
				continue
			print("Nova: Creating your picture...")
			try:
				mime_type, image_bytes = generate_image(message, image_api_key)
				image_path = save_generated_image(mime_type, image_bytes)
				reply = f"Picture saved to: {image_path}"
				webbrowser.open(image_path.as_uri())
			except (RuntimeError, ValueError, OSError) as error:
				history.pop()
				print(f"Nova: Image creation failed: {error}")
				continue
		if not images and not generate_picture:
			reply = answer_greeting(message)
			if reply is None:
				reply = answer_ping_time(message)
			if reply is None:
				reply = answer_roblox_game(message)

		if reply is None:
			if not ensure_local_setup():
				history.pop()
				continue
			try:
				reply = request_chat(
					build_messages(history),
					images=images,
					stream=True,
				)
			except (RuntimeError, ValueError, KeyError) as error:
				history.pop()
				print(f"\nNova: Request failed: {error}")
				continue
			print()
		else:
			print(f"Nova: {reply}")

		history.append({"role": "assistant", "content": reply})
		try:
			save_history(history)
		except RuntimeError as error:
			print(f"Nova: {error}")


if __name__ == "__main__":
	main()
