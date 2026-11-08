# Nova for Android

[**Download the latest Nova APK**](https://github.com/KingJoker779/Nova/releases/latest/download/Nova.apk)

Nova is a local AI chatbot. The Android app uses llama.cpp inside the app and
the same small Qwen 3.5 0.8B model as the desktop chatbot. It does not require
Ollama or another chatbot app.

The app is text-chat only for now. On first launch, tap **Download AI model**
to download about 533 MB over the internet; Wi-Fi is recommended. The model
stays in the app's private storage. After setup, ordinary replies are generated
on the phone without an internet connection or an AI service account.

The model is a small general-purpose assistant. It can help across many topics,
but no AI can answer literally everything, and this local model can make
mistakes or lack current information. Phones may generate replies more slowly
than computers.

To install the APK, download it to an Android 13 or newer phone and open the
downloaded file. If Android asks, allow your browser or file manager to install
unknown apps, then follow the installation prompt. The app's first launch
downloads its approximately 533 MB AI model; Wi-Fi is recommended.

## Build the app on Windows

1. Install Android Studio from <https://developer.android.com/studio>.
2. In Android Studio's SDK Manager, install Android SDK Platform 36, Android
   SDK Build-Tools, NDK 29.0.13113456, and CMake 3.31.6.
3. Double-click **Prepare Nova for Android.bat**. It downloads the pinned llama.cpp
   Android library source. This step needs internet.
4. Open this `android` folder in Android Studio and wait for Gradle sync. If
   prompted, allow Android Studio to install missing SDK components.
5. Connect an Android phone with USB debugging enabled and press **Run**, or
   select **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
6. Android Studio creates the APK at
   `app\build\outputs\apk\debug\app-debug.apk`. Copy it to the phone and open
   it to install. The phone must run Android 13 (API 33) or newer and have an
   ARM64 or x86-64 processor.

You can also try **Build Nova for Android.bat** after Android Studio and its SDK
components have been installed.

The Android application ID is `com.nova.android`. Android treats this as a new
app rather than an update to older `com.mychatbot.android` builds, so the old
app's private data and downloaded model do not transfer automatically.

## Download and licensing

The app downloads the Qwen model from
<https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF>. Its bundled Android
inference library is built from llama.cpp tag `b12193`. The model's SHA-256 is
checked before it is loaded.
