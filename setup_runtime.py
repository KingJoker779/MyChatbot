"""Download Nova's private CPU runtime and local model."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import re
import shutil
import stat
import sys
import tarfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(
	os.environ.get(
		"NOVA_DATA_DIR",
		os.environ.get("CHATBOT_DATA_DIR", Path(__file__).resolve().parent),
	)
).resolve()
RUNTIME_DIR = ROOT / "runtime"
MODEL_DIR = ROOT / "models"
MODEL_FILES = {
	"Qwen3.5-0.8B-Q4_K_M.gguf": (
		532517120,
		"bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517",
	),
	"mmproj-F16.gguf": (
		204987232,
		"56e4c6cfe73b0c82e3e82bc518d7591997e61d81f723fc41a586f4fa69ea2453",
	),
}
MODEL_URL = (
	"https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/resolve/main/"
)
LLAMA_RELEASE_URL = (
	"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b12193"
)


def request_bytes(url, *, accept="application/octet-stream"):
	request = Request(
		url,
		headers={"Accept": accept, "User-Agent": "LocalChatbot-Setup/1.0"},
	)
	with urlopen(request, timeout=60) as response:
		return response.read()


def download_file(url, destination, expected_size=None):
	destination.parent.mkdir(parents=True, exist_ok=True)
	temporary = destination.with_name(destination.name + ".download")
	request = Request(url, headers={"User-Agent": "LocalChatbot-Setup/1.0"})
	try:
		with urlopen(request, timeout=120) as response, temporary.open("wb") as file:
			total = int(response.headers.get("Content-Length", expected_size or 0))
			downloaded = 0
			last_reported = -1
			while True:
				chunk = response.read(1024 * 1024)
				if not chunk:
					break
				file.write(chunk)
				downloaded += len(chunk)
				if total:
					percent = min(downloaded * 100 // total, 100)
					if percent // 10 > last_reported // 10:
						print(f"  {percent}%")
						last_reported = percent
		if expected_size is not None and downloaded != expected_size:
			raise RuntimeError(
				f"Downloaded {downloaded:,} bytes for {destination.name}; "
				f"expected {expected_size:,}."
			)
		temporary.replace(destination)
	except (HTTPError, URLError, OSError, TimeoutError) as error:
		raise RuntimeError(f"Could not download {destination.name}: {error}") from error
	finally:
		if temporary.exists():
			temporary.unlink()


def sha256_file(path):
	digest = hashlib.sha256()
	with path.open("rb") as file:
		for chunk in iter(lambda: file.read(1024 * 1024), b""):
			digest.update(chunk)
	return digest.hexdigest()


def get_runtime_asset():
	machine = platform.machine().lower()
	is_arm = machine in {"arm64", "aarch64"}
	is_x64 = machine in {"x86_64", "amd64", "x64"}
	if not is_arm and not is_x64:
		raise RuntimeError(f"This processor architecture is not supported: {machine}")
	if sys.platform == "win32":
		asset = (
			"llama-b12193-bin-win-cpu-arm64.zip"
			if is_arm
			else "llama-b12193-bin-win-cpu-x64.zip"
		)
	elif sys.platform == "darwin":
		asset = (
			"llama-b12193-bin-macos-arm64.tar.gz"
			if is_arm
			else "llama-b12193-bin-macos-x64.tar.gz"
		)
	elif sys.platform.startswith("linux"):
		asset = (
			"llama-b12193-bin-ubuntu-arm64.tar.gz"
			if is_arm
			else "llama-b12193-bin-ubuntu-x64.tar.gz"
		)
	else:
		raise RuntimeError(f"This operating system is not supported: {sys.platform}")

	try:
		release = json.loads(request_bytes(LLAMA_RELEASE_URL, accept="application/json"))
	except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
		raise RuntimeError(f"Could not check the llama.cpp release: {error}") from error
	if not isinstance(release, dict) or not isinstance(release.get("assets"), list):
		raise RuntimeError("The llama.cpp release API returned an unexpected response.")
	for item in release["assets"]:
		if (
			isinstance(item, dict)
			and item.get("name") == asset
		):
			download_url = item.get("browser_download_url")
			if (
				not isinstance(download_url, str)
				or not download_url.startswith(
					"https://github.com/ggml-org/llama.cpp/releases/download/"
				)
			):
				raise RuntimeError("The llama.cpp release returned an invalid download URL.")
			digest = item.get("digest", "")
			expected_hash = None
			if digest:
				if not isinstance(digest, str) or not re.fullmatch(
					r"sha256:[0-9a-fA-F]{64}", digest
				):
					raise RuntimeError("The llama.cpp release returned an invalid SHA-256 digest.")
				expected_hash = digest[len("sha256:"):].lower()
			size = item.get("size")
			if size is not None and (type(size) is not int or size <= 0):
				raise RuntimeError("The llama.cpp release returned an invalid asset size.")
			return asset, download_url, size, expected_hash
	raise RuntimeError(f"The llama.cpp release does not provide {asset}.")


def is_safe_archive_path(root, member_name):
	posix_name = PurePosixPath(member_name.replace("\\", "/"))
	windows_name = PureWindowsPath(member_name)
	if (
		posix_name.is_absolute()
		or windows_name.is_absolute()
		or windows_name.drive
		or any(":" in part for part in posix_name.parts)
	):
		return False
	reserved_names = {
		"con", "prn", "aux", "nul",
		*(f"com{number}" for number in range(1, 10)),
		*(f"lpt{number}" for number in range(1, 10)),
	}
	if any(part.split(".", 1)[0].casefold() in reserved_names for part in posix_name.parts):
		return False
	if ".." in posix_name.parts or ".." in windows_name.parts:
		return False
	root_path = root.resolve()
	target = (root / Path(*posix_name.parts)).resolve()
	try:
		return os.path.commonpath((str(root_path), str(target))) == str(root_path)
	except ValueError:
		return False


def extract_runtime(archive_path):
	RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
	if zipfile.is_zipfile(archive_path):
		try:
			with zipfile.ZipFile(archive_path) as archive:
				members = archive.infolist()
				for item in members:
					mode = item.external_attr >> 16
					file_type = stat.S_IFMT(mode)
					if (
						not is_safe_archive_path(RUNTIME_DIR, item.filename)
						or file_type not in {0, stat.S_IFREG, stat.S_IFDIR}
					):
						raise RuntimeError(
							"The llama.cpp archive contains an unsafe path or file type."
						)
				bad_member = archive.testzip()
				if bad_member is not None:
					raise RuntimeError(
						f"The llama.cpp archive is damaged at {bad_member}."
					)
				archive.extractall(RUNTIME_DIR)
		except (zipfile.BadZipFile, OSError) as error:
			raise RuntimeError(f"Could not unpack the llama.cpp runtime: {error}") from error
		return

	try:
		with tarfile.open(archive_path, "r:gz") as archive:
			for member in archive.getmembers():
				if not is_safe_archive_path(RUNTIME_DIR, member.name):
					raise RuntimeError("The llama.cpp archive contains an unsafe path.")
				if not (member.isdir() or member.isfile()):
					raise RuntimeError("The llama.cpp archive contains an unsupported file.")
			for member in archive.getmembers():
				target = RUNTIME_DIR / Path(*PurePosixPath(member.name).parts)
				if member.isdir():
					target.mkdir(parents=True, exist_ok=True)
					continue
				target.parent.mkdir(parents=True, exist_ok=True)
				source = archive.extractfile(member)
				if source is None:
					raise RuntimeError(f"Could not read runtime file {member.name}.")
				with source, target.open("wb") as destination:
					shutil.copyfileobj(source, destination)
				target.chmod(member.mode & 0o777)
	except (tarfile.TarError, OSError) as error:
		raise RuntimeError(f"Could not unpack the llama.cpp runtime: {error}") from error


def find_server():
	server_name = "llama-server.exe" if os.name == "nt" else "llama-server"
	return next(RUNTIME_DIR.rglob(server_name), None) if RUNTIME_DIR.exists() else None


def install_runtime():
	if find_server() is not None:
		print("The local AI engine is already installed.")
		return
	asset_name, url, size, expected_hash = get_runtime_asset()
	archive_path = RUNTIME_DIR / asset_name
	print(f"Downloading Nova's CPU engine ({asset_name})...")
	download_file(url, archive_path, size)
	if expected_hash and sha256_file(archive_path) != expected_hash:
		archive_path.unlink()
		raise RuntimeError("The downloaded AI engine failed its SHA-256 check.")
	print("Unpacking the AI engine...")
	try:
		extract_runtime(archive_path)
	finally:
		if archive_path.exists():
			archive_path.unlink()
	if find_server() is None:
		raise RuntimeError("The AI engine download did not contain llama-server.")


def install_models():
	for name, (size, expected_hash) in MODEL_FILES.items():
		destination = MODEL_DIR / name
		if destination.is_file() and destination.stat().st_size == size:
			print(f"Checking {name}...")
			if sha256_file(destination) == expected_hash:
				continue
			destination.unlink()
		print(f"Downloading {name} ({size / 1_000_000:.0f} MB)...")
		download_file(
			MODEL_URL + name + "?download=true",
			destination,
			size,
		)
		if sha256_file(destination) != expected_hash:
			destination.unlink()
			raise RuntimeError(f"{name} failed its SHA-256 check.")


def main():
	try:
		install_runtime()
		install_models()
	except RuntimeError as error:
		print(f"Setup failed: {error}", file=sys.stderr)
		return 1
	print("Setup complete. Nova now has its own local AI engine and model.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
