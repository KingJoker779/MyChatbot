import SwiftUI
import UIKit

struct ContentView: View {
    @StateObject private var llamaState = LlamaState()
    @State private var messages = [
        ChatMessage(
            role: .assistant,
            text: "Hi! I’m Nova. Ask me a question, or ask me to make a picture.",
            imageData: nil
        )
    ]
    @State private var draft = ""
    @State private var imageApiKey = ""
    @State private var statusText = "Local chat is ready when you load a model."
    @State private var isWorking = false
    @State private var showingModels = false
    @State private var showingImageSettings = false

    var body: some View {
        VStack(spacing: 0) {
            header

            Text(statusText)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 18)
                .padding(.vertical, 10)

            ScrollViewReader { scrollProxy in
                ScrollView {
                    LazyVStack(spacing: 14) {
                        ForEach(messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                        if isWorking {
                            HStack {
                                ProgressView()
                                Text("Nova is working…")
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                                Spacer()
                            }
                            .padding(.horizontal, 8)
                            .id("working")
                        }
                    }
                    .padding(16)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: messages.count) { _ in
                    if let lastMessage = messages.last {
                        withAnimation(.easeOut(duration: 0.2)) {
                            scrollProxy.scrollTo(lastMessage.id, anchor: .bottom)
                        }
                    }
                }
            }

            composer
        }
        .background(Color(uiColor: .systemGroupedBackground))
        .sheet(isPresented: $showingModels) {
            NavigationView {
                DrawerView(llamaState: llamaState)
            }
        }
        .sheet(isPresented: $showingImageSettings) {
            ImageSettingsView(apiKey: $imageApiKey)
                .presentationDetents([.medium])
        }
    }

    private var header: some View {
        HStack(spacing: 12) {
            Image(systemName: "sparkles")
                .font(.system(size: 21, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 46, height: 46)
                .background(
                    LinearGradient(
                        colors: [Color.indigo, Color.purple],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    in: RoundedRectangle(cornerRadius: 16, style: .continuous)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text("Nova")
                    .font(.title2.weight(.bold))
                    .foregroundStyle(.primary)
                Text("Your creative AI companion")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Menu {
                Button {
                    showingModels = true
                } label: {
                    Label("Text AI models", systemImage: "cpu")
                }
                Button {
                    showingImageSettings = true
                } label: {
                    Label("Image settings", systemImage: "photo")
                }
            } label: {
                Image(systemName: "slider.horizontal.3")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(Color.indigo)
                    .frame(width: 44, height: 44)
                    .background(Color.indigo.opacity(0.1), in: Circle())
            }
            .accessibilityLabel("Nova settings")
        }
        .padding(.horizontal, 18)
        .padding(.top, 12)
        .padding(.bottom, 8)
        .background(.regularMaterial)
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextField("Message Nova…", text: $draft, axis: .vertical)
                .lineLimit(1...5)
                .font(.body)
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
                .submitLabel(.send)
                .onSubmit(sendMessage)
                .disabled(isWorking)

            Button(action: sendMessage) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(Color.indigo, in: RoundedRectangle(cornerRadius: 15))
            }
            .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isWorking)
            .opacity(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0.55 : 1)
            .accessibilityLabel("Send message")
        }
        .padding(8)
        .background(.background, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Color.primary.opacity(0.08), lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.06), radius: 10, y: 3)
        .padding(.horizontal, 14)
        .padding(.top, 8)
        .padding(.bottom, 10)
    }

    private func sendMessage() {
        let prompt = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !prompt.isEmpty, !isWorking else { return }

        messages.append(ChatMessage(role: .user, text: prompt, imageData: nil))
        draft = ""
        isWorking = true

        Task {
            defer { isWorking = false }
            if isImagePrompt(prompt) {
                guard !imageApiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                    statusText = "Add your Google AI Studio key in Image settings to create pictures."
                    messages.append(
                        ChatMessage(
                            role: .assistant,
                            text: "I need an image-generation key first. Open the settings button and choose Image settings.",
                            imageData: nil
                        )
                    )
                    return
                }

                statusText = "Creating your picture with Google…"
                do {
                    let imageData = try await generateImage(prompt: prompt, apiKey: imageApiKey)
                    messages.append(
                        ChatMessage(role: .assistant, text: "Here’s your picture.", imageData: imageData)
                    )
                    statusText = "Picture created. Image generation uses the online service."
                } catch {
                    statusText = "Picture creation failed."
                    messages.append(
                        ChatMessage(
                            role: .assistant,
                            text: "I couldn’t create that picture: \(error.localizedDescription)",
                            imageData: nil
                        )
                    )
                }
            } else {
                statusText = "Thinking locally…"
                let reply = await llamaState.complete(text: prompt)
                if reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    statusText = "Load a local text model from Text AI models to chat offline."
                    messages.append(
                        ChatMessage(
                            role: .assistant,
                            text: "I don’t have a text model loaded yet. Open settings → Text AI models to download or load one.",
                            imageData: nil
                        )
                    )
                } else {
                    statusText = "Text chat runs locally on this device."
                    messages.append(
                        ChatMessage(role: .assistant, text: reply.trimmingCharacters(in: .whitespacesAndNewlines), imageData: nil)
                    )
                }
            }
        }
    }

    private func isImagePrompt(_ prompt: String) -> Bool {
        let pattern =
            #"\b(?:make|create|generate|draw|paint|design)\b.{0,80}\b(?:image|picture|photo|illustration|artwork|logo|wallpaper|portrait)\b|\b(?:image|picture|photo|illustration|artwork|logo|wallpaper|portrait)\s+of\b"#
        return prompt.range(of: pattern, options: [.regularExpression, .caseInsensitive, .dotMatchesLineSeparators]) != nil
    }

    private func generateImage(prompt: String, apiKey: String) async throws -> Data {
        guard prompt.count <= 4_000 else {
            throw ImageGenerationError.message("Image prompts must be 4,000 characters or fewer.")
        }
        guard let url = URL(string: Self.imageAPIURL) else {
            throw ImageGenerationError.message("The image service URL is invalid.")
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 180
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey.trimmingCharacters(in: .whitespacesAndNewlines), forHTTPHeaderField: "x-goog-api-key")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "contents": [["parts": [["text": prompt]]]],
            "generationConfig": ["responseModalities": ["TEXT", "IMAGE"]],
        ])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw ImageGenerationError.message("Google returned an invalid image response.")
        }
        let decoded = try? JSONDecoder().decode(GeminiImageResponse.self, from: data)
        guard (200...299).contains(httpResponse.statusCode) else {
            throw ImageGenerationError.message(
                decoded?.error?.message ?? "Google image generation failed (HTTP \(httpResponse.statusCode))."
            )
        }
        for candidate in decoded?.candidates ?? [] {
            for part in candidate.content?.parts ?? [] {
                guard let encoded = part.inlineData?.data,
                      let imageData = Data(base64Encoded: encoded, options: .ignoreUnknownCharacters),
                      !imageData.isEmpty else {
                    continue
                }
                return imageData
            }
        }
        throw ImageGenerationError.message("Google’s response did not contain a generated picture.")
    }

    private static let imageAPIURL =
        "https://generativelanguage.googleapis.com/v1beta/models/" +
        "gemini-2.5-flash-image:generateContent"

    struct DrawerView: View {
        @ObservedObject var llamaState: LlamaState
        @Environment(\.dismiss) private var dismiss
        @State private var showingHelp = false

        private func delete(at offsets: IndexSet) {
            offsets.forEach { offset in
                let model = llamaState.downloadedModels[offset]
                let fileURL = llamaState.getDocumentsDirectory().appendingPathComponent(model.filename)
                do {
                    try FileManager.default.removeItem(at: fileURL)
                } catch {
                    print("Error deleting file: \(error)")
                }
            }
            llamaState.downloadedModels.remove(atOffsets: offsets)
        }

        var body: some View {
            List {
                Section(header: Text("Download a model")) {
                    InputButton(llamaState: llamaState)
                }
                Section(header: Text("Downloaded models")) {
                    ForEach(llamaState.downloadedModels) { model in
                        DownloadButton(
                            llamaState: llamaState,
                            modelName: model.name,
                            modelUrl: model.url,
                            filename: model.filename
                        )
                    }
                    .onDelete(perform: delete)
                }
                Section(header: Text("Available models")) {
                    ForEach(llamaState.undownloadedModels) { model in
                        DownloadButton(
                            llamaState: llamaState,
                            modelName: model.name,
                            modelUrl: model.url,
                            filename: model.filename
                        )
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Text AI models")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Help") { showingHelp = true }
                }
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Done") { dismiss() }
                }
            }
            .sheet(isPresented: $showingHelp) {
                NavigationView {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Use a GGUF model from a trusted source.")
                        Text("Downloaded models stay in Nova’s private app storage.")
                        Spacer()
                    }
                    .padding()
                    .navigationTitle("Model help")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .navigationBarTrailing) {
                            Button("Done") { showingHelp = false }
                        }
                    }
                }
            }
        }
    }
}

private struct ChatMessage: Identifiable {
    enum Role: Equatable {
        case user
        case assistant
    }

    let id = UUID()
    let role: Role
    let text: String
    let imageData: Data?
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 48) }
            VStack(alignment: .leading, spacing: 8) {
                Text(message.text)
                    .font(.body)
                    .textSelection(.enabled)
                if let imageData = message.imageData,
                   let image = UIImage(data: imageData) {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: 320, maxHeight: 420)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }
            }
            .foregroundStyle(message.role == .user ? Color.white : Color.primary)
            .padding(14)
            .background(
                message.role == .user ? Color.indigo : Color(uiColor: .secondarySystemGroupedBackground),
                in: RoundedRectangle(cornerRadius: 18, style: .continuous)
            )
            if message.role == .assistant { Spacer(minLength: 48) }
        }
    }
}

private struct ImageSettingsView: View {
    @Binding var apiKey: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            Form {
                Section {
                    SecureField("Google AI Studio API key", text: $apiKey)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } header: {
                    Text("Image generation")
                } footer: {
                    Text("Nova sends image prompts to Google. The key stays in memory for this app session and is not saved. Usage may be limited or cost money.")
                }

                Link(
                    "Get an API key",
                    destination: URL(string: "https://aistudio.google.com/apikey")!
                )
            }
            .navigationTitle("Image settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

private struct GeminiImageResponse: Decodable {
    let candidates: [Candidate]?
    let error: ServiceError?

    struct Candidate: Decodable {
        let content: Content?
    }

    struct Content: Decodable {
        let parts: [Part]?
    }

    struct Part: Decodable {
        let inlineData: InlineData?
    }

    struct InlineData: Decodable {
        let mimeType: String?
        let data: String?
    }

    struct ServiceError: Decodable {
        let message: String?
    }
}

private enum ImageGenerationError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let text):
            return text
        }
    }
}
