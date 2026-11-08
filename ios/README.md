# iOS status

`AppTemplate` now has a Nova-branded SwiftUI chat screen with online picture
generation through Google's Gemini image API. Image generation needs each
user's own Google AI Studio API key; the key is held in memory only, and image
prompts are sent to Google. Availability, rate limits, and charges depend on
Google's service and account.

The local text-model controls are still based on the upstream llama.cpp sample,
not the desktop or Android Nova model setup. This iOS project has not been
built or tested here, and should not be presented as a verified release.

Building requires macOS, Xcode, and a llama.cpp `llama.xcframework`. A Windows
machine cannot build or sign an iOS app. An installable release also requires
Apple signing and provisioning.

The model picker uses a background `URLSession` for model transfers. iOS does
not require notification permission to complete these transfers; force-quitting
the app can stop them. Picture generation needs internet and an individual
Google AI Studio API key.

The included sample has its own MIT license in `AppTemplate/LICENSE`. No claim
is made that the chatbot's desktop or Android source is part of that license.
