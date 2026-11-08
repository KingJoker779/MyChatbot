package com.nova.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class ModelDownloadService : Service() {
	@Volatile
	private var downloadThread: Thread? = null

	override fun onBind(intent: Intent?): IBinder? = null

	override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
		if (intent?.action != ACTION_DOWNLOAD) {
			stopSelf(startId)
			return START_NOT_STICKY
		}

		downloadActive = true
		createNotificationChannel()
		if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
			startForeground(
				NOTIFICATION_ID,
				buildNotification("Starting model download…", 0, true),
				ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
			)
		} else {
			startForeground(NOTIFICATION_ID, buildNotification("Starting model download…", 0, true))
		}
		if (downloadThread?.isAlive == true) return START_NOT_STICKY
		val wakeLock = getSystemService(PowerManager::class.java)
			.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "$packageName:model-download")
			.apply {
				setReferenceCounted(false)
				acquire()
			}

		downloadThread = Thread({
			try {
				downloadModel()
				sendStatus(ACTION_COMPLETED, "AI model downloaded and verified.")
			} catch (error: Exception) {
				sendStatus(
					ACTION_FAILED,
					error.message ?: "The AI model download failed.",
				)
			} finally {
				downloadActive = false
				if (wakeLock.isHeld) wakeLock.release()
				stopForeground(STOP_FOREGROUND_REMOVE)
				stopSelf(startId)
			}
		}, "Nova-model-download").apply {
			isDaemon = true
			start()
		}
		return START_NOT_STICKY
	}

	private fun downloadModel() {
		val modelDirectory = File(filesDir, "models")
		if (!modelDirectory.exists() && !modelDirectory.mkdirs()) {
			throw IOException("Couldn't create the model folder.")
		}
		val modelFile = File(modelDirectory, MODEL_NAME)
		if (modelFile.isFile && modelFile.length() == MODEL_SIZE) {
			updateProgress(MODEL_SIZE, MODEL_SIZE)
			if (sha256(modelFile) == MODEL_SHA256) return
		}
		if (modelFile.exists() && !modelFile.delete()) {
			throw IOException("The incomplete model file couldn't be removed.")
		}

		val temporaryFile = File(modelDirectory, "$MODEL_NAME.download")
		if (temporaryFile.exists() && !temporaryFile.delete()) {
			throw IOException("Couldn't remove the previous incomplete download.")
		}
		val connection = URL(MODEL_URL).openConnection() as HttpURLConnection
		connection.connectTimeout = 30_000
		connection.readTimeout = 120_000
		connection.setRequestProperty("User-Agent", "Nova-Android/1.0")
		try {
			if (connection.responseCode !in 200..299) {
				throw IOException("Model download failed (HTTP ${connection.responseCode}).")
			}
			connection.inputStream.use { input ->
				FileOutputStream(temporaryFile).use { output ->
					val buffer = ByteArray(1024 * 1024)
					var downloaded = 0L
					var lastPercent = -1
					while (true) {
						if (Thread.currentThread().isInterrupted) {
							throw IOException("The model download was interrupted.")
						}
						val count = input.read(buffer)
						if (count < 0) break
						output.write(buffer, 0, count)
						downloaded += count
						val percent = (downloaded * 100 / MODEL_SIZE).toInt().coerceIn(0, 100)
						if (percent != lastPercent) {
							lastPercent = percent
							updateProgress(downloaded, MODEL_SIZE)
						}
					}
					output.fd.sync()
				}
			}
		} finally {
			connection.disconnect()
		}

		if (temporaryFile.length() != MODEL_SIZE) {
			temporaryFile.delete()
			throw IOException("The model download was incomplete. Please try again.")
		}
		if (sha256(temporaryFile) != MODEL_SHA256) {
			temporaryFile.delete()
			throw IOException("The model download failed its integrity check.")
		}
		if (!temporaryFile.renameTo(modelFile)) {
			throw IOException("Couldn't save the downloaded model.")
		}
	}

	private fun sha256(file: File): String {
		val digest = MessageDigest.getInstance("SHA-256")
		file.inputStream().buffered().use { input ->
			val buffer = ByteArray(1024 * 1024)
			while (true) {
				val count = input.read(buffer)
				if (count < 0) break
				digest.update(buffer, 0, count)
			}
		}
		return digest.digest().joinToString("") { "%02x".format(it) }
	}

	private fun updateProgress(downloaded: Long, total: Long) {
		val percent = (downloaded * 100 / total).toInt().coerceIn(0, 100)
		val megabytes = downloaded / (1024 * 1024)
		val totalMegabytes = total / (1024 * 1024)
		val message = "Downloading AI model: $percent% ($megabytes of $totalMegabytes MB)"
		sendStatus(ACTION_PROGRESS, message, percent)
		val manager = getSystemService(NotificationManager::class.java)
		manager.notify(
			NOTIFICATION_ID,
			buildNotification(message, percent, true),
		)
	}

	private fun sendStatus(action: String, message: String, percent: Int = 0) {
		sendBroadcast(
			Intent(action)
				.setPackage(packageName)
				.putExtra(EXTRA_MESSAGE, message)
				.putExtra(EXTRA_PROGRESS, percent),
		)
	}

	private fun createNotificationChannel() {
		val manager = getSystemService(NotificationManager::class.java)
		manager.createNotificationChannel(
			NotificationChannel(
				CHANNEL_ID,
				"Nova model downloads",
				NotificationManager.IMPORTANCE_LOW,
			).apply {
				description = "Shows progress while Nova downloads its text AI model."
			},
		)
	}

	private fun buildNotification(message: String, progress: Int, ongoing: Boolean): Notification {
		val openApp = PendingIntent.getActivity(
			this,
			0,
			Intent(this, MainActivity::class.java),
			PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
		)
		return NotificationCompat.Builder(this, CHANNEL_ID)
			.setSmallIcon(android.R.drawable.stat_sys_download)
			.setContentTitle("Nova AI setup")
			.setContentText(message)
			.setContentIntent(openApp)
			.setOnlyAlertOnce(true)
			.setOngoing(ongoing)
			.setProgress(100, progress, progress == 0)
			.setPriority(NotificationCompat.PRIORITY_LOW)
			.build()
	}

	companion object {
		const val ACTION_DOWNLOAD = "com.nova.android.DOWNLOAD_MODEL"
		const val ACTION_PROGRESS = "com.nova.android.MODEL_DOWNLOAD_PROGRESS"
		const val ACTION_COMPLETED = "com.nova.android.MODEL_DOWNLOAD_COMPLETED"
		const val ACTION_FAILED = "com.nova.android.MODEL_DOWNLOAD_FAILED"
		const val EXTRA_MESSAGE = "message"
		const val EXTRA_PROGRESS = "progress"

		@Volatile
		var downloadActive = false
			private set

		private const val CHANNEL_ID = "nova_model_downloads"
		private const val NOTIFICATION_ID = 101
		private const val MODEL_NAME = "Qwen3.5-0.8B-Q4_K_M.gguf"
		private const val MODEL_SIZE = 532_517_120L
		private const val MODEL_SHA256 =
			"bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517"
		private const val MODEL_URL =
			"https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/resolve/main/" +
				"Qwen3.5-0.8B-Q4_K_M.gguf?download=true"
	}
}
