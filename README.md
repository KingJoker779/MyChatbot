# Nova

A small, local-first chatbot for desktop and Android. The model and
inference engine are downloaded separately; they are not stored in this
repository.

## Platform status

| Platform | What is included | Status |
| --- | --- | --- |
| Windows | Python source, setup scripts, and a script to build a small EXE | Source/build scripts included; the model downloads on first run |
| Linux | Python source and setup/run scripts | Source included; no prebuilt Linux binary |
| macOS | Python source and setup/run scripts | Source included; no prebuilt macOS app |
| Android | Native app source under [`android`](./android) | Source only; no verified APK included |
| iOS | Upstream llama.cpp SwiftUI sample under [`ios/AppTemplate`](./ios/AppTemplate) | Prototype only; not yet integrated with this chatbot or verified as a build |

The iOS folder is a starting sample, not a finished iOS release of Nova.
Building it requires a Mac with Xcode and the llama.cpp Apple framework. Details
and limitations are in [`ios/README.md`](./ios/README.md).

## Desktop setup

On Windows, run **Setup chatbot.bat**, then **Run chatbot.bat**. To build the
small Windows EXE, run **Build Windows app.bat**. The EXE does not contain the
model or inference engine; the first launch downloads them to the user's local
application data folder.

On Linux or macOS, install Python 3 and run:

```sh
sh setup-chatbot.sh
sh run-chatbot.sh
```

The first setup needs internet and about 1 GB of storage. After setup, desktop
answers are generated locally. A small model can make mistakes or lack current
information.

## Android

See [`android/README.md`](./android/README.md) for the Android Studio, SDK, NDK,
and build instructions. The project downloads its pinned llama.cpp source when
prepared. The app downloads its model on first launch. Android source is
included, but an APK has not been verified for this repository.

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
