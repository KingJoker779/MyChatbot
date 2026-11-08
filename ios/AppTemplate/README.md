# Nova for iOS (prototype)

This SwiftUI prototype has Nova chat, local GGUF text-model support through
llama.cpp, and online image generation through Google's Gemini image API.
Image generation requires each user to provide their own Google AI Studio API
key in Image settings. Prompts are sent to Google; availability, limits, and
charges depend on the user's Google account.

Model downloads use a background `URLSession`, so iOS can continue a transfer
after the app is suspended. iOS does not require notification permission for
the transfer itself. A force-quit by the user can stop background work.

The local model library and model picker are still based on the upstream
llama.cpp sample; this is not yet a complete cross-platform Nova release.
Building requires macOS, Xcode, and a llama.cpp `llama.xcframework`.

For upstream usage instructions and performance stats, see
<https://github.com/ggml-org/llama.cpp/discussions/4508>.


### Building
First llama.cpp need to be built and a XCFramework needs to be created. This can be done by running
the following script from the llama.cpp project root:
```console
$ ./build-xcframework.sh
```
Open `llama.swiftui.xcodeproj` project in Xcode and you should be able to build and run the app on
a simulator or a real device.

To use the framework with a different project, the XCFramework can be added to the project by
adding `build-apple/llama.xcframework` by dragging and dropping it into the project navigator, or
by manually selecting the framework in the "Frameworks, Libraries, and Embedded Content" section
of the project settings.

![image](https://github.com/ggml-org/llama.cpp/assets/1991296/2b40284f-8421-47a2-b634-74eece09a299)

Video demonstration:

https://github.com/bachittle/llama.cpp/assets/39804642/e290827a-4edb-4093-9642-2a5e399ec545
