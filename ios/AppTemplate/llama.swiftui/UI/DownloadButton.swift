import SwiftUI
import Foundation

struct DownloadButton: View {
    @ObservedObject private var llamaState: LlamaState
    @ObservedObject private var downloader = BackgroundModelDownloader.shared
    private let modelName: String
    private let modelUrl: String
    private let filename: String

    init(llamaState: LlamaState, modelName: String, modelUrl: String, filename: String) {
        self.llamaState = llamaState
        self.modelName = modelName
        self.modelUrl = modelUrl
        self.filename = filename
    }

    private var fileURL: URL {
        llamaState.getDocumentsDirectory().appendingPathComponent(filename)
    }

    private var isDownloaded: Bool {
        downloader.finishedFiles.contains(filename) ||
            FileManager.default.fileExists(atPath: fileURL.path)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if downloader.progressByFilename[filename] != nil {
                Button {
                    downloader.cancel(filename: filename)
                } label: {
                    Label("Cancel download", systemImage: "xmark.circle")
                }
                ProgressView(
                    value: downloader.progressByFilename[filename] ?? 0,
                    total: 1
                )
                Text(
                    "Downloading \(modelName) " +
                        "\(Int((downloader.progressByFilename[filename] ?? 0) * 100))%"
                )
                .font(.caption)
                .foregroundStyle(.secondary)
            } else if isDownloaded {
                Button {
                    do {
                        try llamaState.loadModel(modelUrl: fileURL)
                    } catch {
                        downloader.setError(error.localizedDescription, filename: filename)
                    }
                } label: {
                    Label("Load \(modelName)", systemImage: "cpu")
                }
            } else {
                Button {
                    downloader.download(modelName: modelName, url: modelUrl, filename: filename)
                } label: {
                    Label("Download \(modelName)", systemImage: "arrow.down.circle")
                }
            }

            if let error = downloader.errorByFilename[filename] {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
    }
}

final class BackgroundModelDownloader: NSObject, ObservableObject, URLSessionDownloadDelegate {
    static let sessionIdentifier = "com.nova.ios.model-downloads"
    static let shared = BackgroundModelDownloader()

    @Published private(set) var progressByFilename: [String: Double] = [:]
    @Published private(set) var finishedFiles: Set<String> = []
    @Published private(set) var errorByFilename: [String: String] = [:]

    private var session: URLSession!
    private var backgroundCompletionHandler: (() -> Void)?

    private override init() {
        super.init()
        let configuration = URLSessionConfiguration.background(
            withIdentifier: Self.sessionIdentifier
        )
        configuration.isDiscretionary = false
        configuration.sessionSendsLaunchEvents = true
        session = URLSession(
            configuration: configuration,
            delegate: self,
            delegateQueue: OperationQueue.main
        )
        session.getAllTasks { [weak self] tasks in
            DispatchQueue.main.async {
                for task in tasks {
                    guard let info = Self.info(for: task) else { continue }
                    self?.progressByFilename[info.filename] = task.progress.fractionCompleted
                }
            }
        }
    }

    func download(modelName: String, url source: String, filename: String) {
        guard let url = URL(string: source),
              url.scheme?.lowercased() == "https",
              Self.isSafeModelFilename(filename) else {
            setError("Enter a valid HTTPS model link.", filename: filename)
            return
        }
        guard progressByFilename[filename] == nil else { return }

        let info = ModelDownloadInfo(modelName: modelName, url: source, filename: filename)
        guard let description = try? JSONEncoder().encode(info),
              let encoded = String(data: description, encoding: .utf8) else {
            setError("Couldn't prepare the model download.", filename: filename)
            return
        }
        let task = session.downloadTask(with: url)
        task.taskDescription = encoded
        errorByFilename.removeValue(forKey: filename)
        progressByFilename[filename] = 0
        task.resume()
    }

    func cancel(filename: String) {
        session.getAllTasks { [weak self] tasks in
            let matching = tasks.filter { Self.info(for: $0)?.filename == filename }
            matching.forEach { $0.cancel() }
            DispatchQueue.main.async {
                self?.progressByFilename.removeValue(forKey: filename)
                self?.setError("Download cancelled.", filename: filename)
            }
        }
    }

    func setError(_ message: String, filename: String) {
        errorByFilename[filename] = message
        progressByFilename.removeValue(forKey: filename)
    }

    func setBackgroundCompletionHandler(_ handler: @escaping () -> Void) {
        backgroundCompletionHandler = handler
    }

    func urlSession(
        _ session: URLSession,
        downloadTask: URLSessionDownloadTask,
        didWriteData bytesWritten: Int64,
        totalBytesWritten: Int64,
        totalBytesExpectedToWrite: Int64
    ) {
        guard let info = Self.info(for: downloadTask),
              totalBytesExpectedToWrite > 0 else {
            return
        }
        progressByFilename[info.filename] = min(
            Double(totalBytesWritten) / Double(totalBytesExpectedToWrite),
            1
        )
    }

    func urlSession(
        _ session: URLSession,
        downloadTask: URLSessionDownloadTask,
        didFinishDownloadingTo location: URL
    ) {
        guard let info = Self.info(for: downloadTask) else { return }
        guard let response = downloadTask.response as? HTTPURLResponse,
              (200...299).contains(response.statusCode) else {
            setError("The model server returned an error.", filename: info.filename)
            return
        }

        let destination = FileManager.default.urls(
            for: .documentDirectory,
            in: .userDomainMask
        )[0].appendingPathComponent(info.filename)
        do {
            if FileManager.default.fileExists(atPath: destination.path) {
                try FileManager.default.removeItem(at: destination)
            }
            try FileManager.default.moveItem(at: location, to: destination)
            progressByFilename.removeValue(forKey: info.filename)
            finishedFiles.insert(info.filename)
            errorByFilename.removeValue(forKey: info.filename)
        } catch {
            setError("Couldn't save the downloaded model: \(error.localizedDescription)", filename: info.filename)
        }
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didCompleteWithError error: Error?
    ) {
        guard let error,
              let info = Self.info(for: task) else {
            return
        }
        if let urlError = error as? URLError, urlError.code == .cancelled {
            return
        }
        setError("Download failed: \(error.localizedDescription)", filename: info.filename)
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        let completionHandler = backgroundCompletionHandler
        backgroundCompletionHandler = nil
        DispatchQueue.main.async {
            completionHandler?()
        }
    }

    private static func info(for task: URLSessionTask) -> ModelDownloadInfo? {
        guard let description = task.taskDescription,
              let data = description.data(using: .utf8) else {
            return nil
        }
        return try? JSONDecoder().decode(ModelDownloadInfo.self, from: data)
    }

    static func isSafeModelFilename(_ filename: String) -> Bool {
        !filename.isEmpty &&
            filename != "." &&
            filename != ".." &&
            URL(fileURLWithPath: filename).lastPathComponent == filename &&
            !filename.contains("\\")
    }
}

private struct ModelDownloadInfo: Codable {
    let modelName: String
    let url: String
    let filename: String
}
