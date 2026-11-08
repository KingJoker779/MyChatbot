# Nova

[**Download the Nova Android APK**](https://github.com/KingJoker779/Nova/releases/latest/download/Nova.apk) · [Other downloads](https://github.com/KingJoker779/Nova/releases/latest)

A small, local-first chatbot for desktop and Android. The model and
inference engine are downloaded separately; they are not stored in this
repository.

Nova can also create a picture when you ask for one. Image creation sends
that prompt to Google's Gemini image service; it is not generated locally.
Each person must provide their own Google AI Studio API key. Google controls
availability, rate limits, and any applicable charges, so image generation is
not guaranteed to be unlimited or free. Do not put an API key in the app,
repository, or a public release.

## Platform status

| Platform | What is included | Status |
| --- | --- | --- |
| Windows | Python source, setup scripts, and a script to build a small EXE | Source/build scripts included; the model downloads on first run |
| Linux | Python source and setup/run scripts | Source included; no prebuilt Linux binary |
| macOS | Python source and setup/run scripts | Source included; no prebuilt macOS app |
| Android | Native app source under [`android`](./android) and APK on the [Releases page](https://github.com/KingJoker779/Nova/releases/latest) | APK built automatically for tagged releases |
| iOS | Nova-branded SwiftUI prototype under [`ios/AppTemplate`](./ios/AppTemplate) | Image creation and background model downloads added; requires macOS/Xcode and remains unverified |

The iOS folder is a prototype, not a finished iOS release. Building it requires
a Mac with Xcode and the llama.cpp Apple framework. Details and limitations are
in [`ios/README.md`](./ios/README.md).

## Desktop setup

On Windows, run **Setup Nova.bat**, then **Run Nova.bat**. To build the small
Windows EXE, run **Build Nova for Windows.bat**. The EXE does not contain the
model or inference engine; the first launch downloads them to the user's local
application data folder.

On Linux or macOS, install Python 3 and run:

```sh
sh setup-nova.sh
sh run-nova.sh
```

The first setup needs internet and about 1 GB of storage. After setup, desktop
answers are generated locally. A small model can make mistakes or lack current
information. To create a picture, ask Nova to draw, make, or generate an image.
The desktop version asks for a Google AI Studio API key (or reads
`GEMINI_API_KEY` from the environment), saves the picture under
`generated_images`, and opens it with your default browser. Get a key from
<https://aistudio.google.com/apikey>. Image prompts are sent to Google.

## Android

Download [Nova.apk](https://github.com/KingJoker779/Nova/releases/latest/download/Nova.apk)
from the latest GitHub release, open it on an Android 13 or newer phone, and
follow Android's prompts to install it. The app supports ARM64 and x86-64
phones. Tap **Image settings** and enter your own Google AI Studio API key to
create pictures in the chat. The key stays in memory for the current app
session; it is not saved. Image prompts are sent to Google. Download the
533 MB local text model with **Download text AI** if you want regular text
chat. The Android app asks permission for download notifications and uses a
foreground service so the download can continue while you use another app.

See [`android/README.md`](./android/README.md) for Android Studio and source
build instructions.

## Tests

Run the desktop regression tests with Python:

```sh
python -m unittest discover -s tests -p "test_*.py"
```

## Repository contents and privacy

Chat history, downloaded models, downloaded inference engines, and generated
build outputs are intentionally excluded. Chat history stays on the device
where it was created.

This repository does not yet declare a project-wide license. The iOS sample
retains its upstream MIT license; see
[`ios/AppTemplate/LICENSE`](./ios/AppTemplate/LICENSE).
