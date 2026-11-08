import SwiftUI
import UIKit

@main
struct NovaApp: App {
    @UIApplicationDelegateAdaptor(NovaAppDelegate.self) private var appDelegate

    init() {
        _ = BackgroundModelDownloader.shared
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

final class NovaAppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        handleEventsForBackgroundURLSession identifier: String,
        completionHandler: @escaping () -> Void
    ) {
        guard identifier == BackgroundModelDownloader.sessionIdentifier else {
            completionHandler()
            return
        }
        BackgroundModelDownloader.shared.setBackgroundCompletionHandler(completionHandler)
    }
}
