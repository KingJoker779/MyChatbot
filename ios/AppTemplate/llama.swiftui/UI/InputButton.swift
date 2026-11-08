import SwiftUI
import Foundation

struct InputButton: View {
    @ObservedObject var llamaState: LlamaState
    @ObservedObject private var downloader = BackgroundModelDownloader.shared
    @State private var inputLink = ""

    private var model: (name: String, filename: String)? {
        guard let url = URL(string: inputLink.trimmingCharacters(in: .whitespacesAndNewlines)),
              url.scheme?.lowercased() == "https",
              let filename = url.lastPathComponent.removingPercentEncoding,
              filename.lowercased().hasSuffix(".gguf"),
              BackgroundModelDownloader.isSafeModelFilename(filename) else {
            return nil
        }
        return (filename, filename)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            TextField("Paste a HTTPS GGUF model link", text: $inputLink)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.URL)

            if let model {
                if downloader.progressByFilename[model.filename] != nil {
                    Button("Cancel download") {
                        downloader.cancel(filename: model.filename)
                    }
                    ProgressView(
                        value: downloader.progressByFilename[model.filename] ?? 0,
                        total: 1
                    )
                } else if FileManager.default.fileExists(
                    atPath: llamaState.getDocumentsDirectory()
                        .appendingPathComponent(model.filename).path
                ) || downloader.finishedFiles.contains(model.filename) {
                    Button("Load \(model.name)") {
                        do {
                            try llamaState.loadModel(
                                modelUrl: llamaState.getDocumentsDirectory()
                                    .appendingPathComponent(model.filename)
                            )
                        } catch {
                            downloader.setError(
                                error.localizedDescription,
                                filename: model.filename
                            )
                        }
                    }
                } else {
                    Button("Download \(model.name)") {
                        downloader.download(
                            modelName: model.name,
                            url: inputLink,
                            filename: model.filename
                        )
                    }
                }

                if let error = downloader.errorByFilename[model.filename] {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            } else {
                Text("Use a direct HTTPS link to a GGUF model file.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}
